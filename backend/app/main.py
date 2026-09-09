from uuid import UUID

from openai import OpenAI
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .agents import AgentContext, KnowledgeSearchAgent, OrchestratorAgent, ReflectionAgent, attach_bom_warehouse_recommendations
from .bom import consolidate_bom
from .costing import build_cost_sheet
from .db import close_pool, run_migrations, start_pool
from .images import ensure_storage
from .repository import get_job, replace_recommendations, save_job, update_detection_labels, update_job_token_usage
from .schemas import AgentTrace, CostSheet, CostSheetRequest, JobResponse, RefineJobRequest, TokenUsageItem, TokenUsageSummary, WarehouseMatchRequest, WarehouseMatchResponse, WarehousePart, WarehouseSearchResult
from .vector_store import save_detection_vectors, search_parts
from .warehouse import list_warehouse_parts, search_warehouse_parts, seed_warehouse, warehouse_summary
from .config import settings


app = FastAPI(title="PartIQ Vision API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    ensure_storage()
    run_migrations()
    start_pool()
    seed_warehouse()


@app.on_event("shutdown")
def on_shutdown() -> None:
    close_pool()

ensure_storage()
app.mount("/storage", StaticFiles(directory="storage"), name="storage")


def append_token_usage(summary: TokenUsageSummary, item: TokenUsageItem) -> TokenUsageSummary:
    items = [*summary.items, item]
    return TokenUsageSummary(
        items=items,
        total_input_tokens=sum(entry.input_tokens for entry in items),
        total_output_tokens=sum(entry.output_tokens for entry in items),
        total_tokens=sum(entry.total_tokens for entry in items),
    )


@app.get("/api/health")
def health() -> dict:
    openai_status = "offline"
    openai_detail = "OPENAI_API_KEY is not configured"
    if settings.openai_api_key:
        try:
            client = OpenAI(api_key=settings.openai_api_key)
            client.responses.create(model=settings.vision_model, input="health", max_output_tokens=16)
            openai_status = "online"
            openai_detail = f"{settings.vision_model} is reachable"
        except Exception as exc:
            openai_status = "offline"
            openai_detail = str(exc)[:300]
    return {
        "status": "ok",
        "database": "postgresql",
        "vector_store": "pgvector",
        "openai": openai_status,
        "openai_detail": openai_detail,
    }


@app.websocket("/ws/screener")
async def screener_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            await websocket.send_json({"type": "ack", "message": message})
    except WebSocketDisconnect:
        return


@app.post("/api/analyze", response_model=JobResponse)
async def analyze(files: list[UploadFile] = File(...), vision_token_mode: str = Form("standard")) -> JobResponse:
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one image")

    token_mode = "optimized" if vision_token_mode == "optimized" else "standard"
    response = await OrchestratorAgent().run(files, token_mode)
    save_job(response)
    vector_usage = save_detection_vectors(response.job_id, response.detections)
    response.token_usage = append_token_usage(response.token_usage, vector_usage)
    update_job_token_usage(response.job_id, response.token_usage)
    return response


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def read_job(job_id: UUID) -> JobResponse:
    record = get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    detections = record["detections"]
    bom = attach_bom_warehouse_recommendations(consolidate_bom(detections), record["recommendations"])
    return JobResponse(
        job_id=str(record["job"]["id"]),
        model_mode=record["job"]["model_mode"],
        vehicle_context=record["job"]["vehicle_context"],
        detections=detections,
        bom=bom,
        cost_sheet=build_cost_sheet(bom),
        token_usage=record["token_usage"],
        recommendations=record["recommendations"],
        agent_trace=record["agent_trace"],
    )


@app.post("/api/jobs/{job_id}/refine", response_model=JobResponse)
def refine_job(job_id: UUID, request: RefineJobRequest) -> JobResponse:
    update_detection_labels(job_id, request.updates)
    record = get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")

    detections = record["detections"]
    bom = consolidate_bom(detections)
    cost_sheet = build_cost_sheet(bom)
    ctx = AgentContext(job_id=str(job_id))
    knowledge = KnowledgeSearchAgent()
    recommendations = knowledge.recommend_from_database(detections, ctx)
    recommendations.extend(knowledge.recommend_bom_alternatives(bom, ctx))
    recommendations.extend(ReflectionAgent().verify(detections, ctx, bom, cost_sheet))
    bom = attach_bom_warehouse_recommendations(bom, recommendations)
    replace_recommendations(job_id, recommendations)
    vector_usage = save_detection_vectors(str(job_id), detections)
    token_usage = append_token_usage(record["token_usage"], vector_usage)
    update_job_token_usage(job_id, token_usage)

    return JobResponse(
        job_id=str(record["job"]["id"]),
        model_mode=f"{record['job']['model_mode']}+user-refined",
        vehicle_context=record["job"]["vehicle_context"],
        detections=detections,
        bom=bom,
        cost_sheet=cost_sheet,
        token_usage=token_usage,
        recommendations=recommendations,
        agent_trace=[
            *record["agent_trace"],
            AgentTrace(
                agent="orchestrator_agent",
                action="rerun_with_user_labels",
                status="complete",
                detail="Recomputed BOM and recommendations from edited labels",
            ),
            *ctx.traces,
        ],
    )


@app.post("/api/jobs/{job_id}/cost-sheet", response_model=CostSheet)
def update_cost_sheet(job_id: UUID, request: CostSheetRequest) -> CostSheet:
    record = get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return build_cost_sheet([item for item in request.bom if item.included])


@app.post("/api/jobs/{job_id}/warehouse-matches", response_model=WarehouseMatchResponse)
def rerun_warehouse_matches(job_id: UUID, request: WarehouseMatchRequest) -> WarehouseMatchResponse:
    record = get_job(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    if request.strategy != "semantic_search":
        raise HTTPException(status_code=400, detail="Unsupported warehouse matching strategy")

    bom = attach_bom_warehouse_recommendations(
        request.bom,
        record["recommendations"],
        strategy=request.strategy,
        reset_selection=True,
    )
    return WarehouseMatchResponse(
        strategy=request.strategy,
        bom=bom,
        cost_sheet=build_cost_sheet([item for item in bom if item.included]),
    )


@app.get("/api/search")
def semantic_search(q: str, limit: int = 10) -> dict:
    return {"results": search_parts(q, limit)}


@app.get("/api/warehouse/parts", response_model=list[WarehousePart])
def read_warehouse_parts(limit: int = 100, offset: int = 0) -> list[dict]:
    return list_warehouse_parts(limit=min(limit, 500), offset=offset)


@app.get("/api/warehouse/search", response_model=list[WarehouseSearchResult])
def warehouse_search(q: str, limit: int = 10) -> list[dict]:
    return search_warehouse_parts(q, limit=min(limit, 50))


@app.get("/api/warehouse/summary")
def read_warehouse_summary() -> dict:
    return warehouse_summary()
