# PartIQ Vision

Browse the [backend](backend/), [frontend](frontend/), [architecture](docs/architecture.md) and [agent prompts](backend/prompts/README.md).

[Repository structure and development guide](docs/repository-guide.md)

Vision LLM powered BOM analysis for vehicle part detection, segmentation-style bounding boxes, part crop capture, confidence scoring, and consolidated multi-image BOM sheets.

## What This Prototype Includes

- FastAPI backend for multi-image upload and analysis
- Optional OpenAI Vision LLM detector using structured JSON output
- Local deterministic demo detector when `OPENAI_API_KEY` is not set
- PostgreSQL persistence for jobs, image detections, crop metadata, and vectorized part records
- `pgvector` powered semantic part lookup
- Synthetic 2,500-row warehouse catalog for stock, material, cost, quantity, consumables, and clustering search
- React dashboard for upload, confidence review, part crops, conditions, and BOM export
- Agentic pipeline with orchestrator, tool agents, knowledge-search agent, and reflection agent
- Human-in-the-loop review with image bounding boxes, editable labels, and BOM recalculation

## Agentic Architecture

The backend is organized as an agent workflow in `backend/app/agents.py`:

- `OrchestratorAgent`: owns the full job lifecycle and execution trace
- `VisionToolAgent`: calls the Vision LLM or demo detector for part detection
- `CropToolAgent`: creates part crop images from model bounding boxes
- `BomToolAgent`: deduplicates multi-image detections into a unique BOM
- `KnowledgeSearchAgent`: searches existing `pgvector` part records for similar or alternate parts
- `ReflectionAgent`: checks whether likely related parts, subparts, consumables, or low-confidence detections are missing from the BOM

This keeps the application ready for later specialized agents: fitment matching, catalog lookup, cost-sheet generation, spare fastener/washer/oil/grease inference, and async job automation.

See the full architecture diagrams in [`docs/architecture.md`](docs/architecture.md).
See the BOM and reflection-agent improvement notes in [`docs/bom-reflection-agents.md`](docs/bom-reflection-agents.md).
See the vision prompt notes in [`docs/vision-detection-prompt.md`](docs/vision-detection-prompt.md).

## Project Structure

```text
backend/   FastAPI app, migrations, Python dependencies, backend container file
frontend/  React/Vite app, Node dependencies, frontend container file
docs/      Architecture and project documentation
output/    Generated build/test/runtime output
```

## Synthetic Parts Warehouse

On backend startup, PostgreSQL seeds a synthetic warehouse catalog with 2,500 stocked part rows. Each row includes SKU, part name, vehicle system, category, material, material grade, baseline condition, unit cost, quantity, reorder level, supplier, visible part numbers, aliases, compatible positions, minute details, included subparts, required consumables, fitment notes, and a `pgvector` embedding.

Warehouse APIs:

```bash
curl http://localhost:8000/api/warehouse/summary
curl "http://localhost:8000/api/warehouse/parts?limit=25"
curl "http://localhost:8000/api/warehouse/search?q=front%20bumper%20clips%20and%20wiring&limit=5"
```

The knowledge-search agent now checks this warehouse first and returns clustered stock candidates with SKU references for later BOM cost-sheet matching.

## Review And Refinement

After analysis, the dashboard reloads the uploaded image and overlays bounding boxes for each detected part. Users can edit part labels, category, material, condition, visible part number, and notes, then run the label refinement step. The backend applies those corrections, refreshes vectors, recomputes the BOM, and reruns recommendation/reflection agents.

Before analysis, the orchestrator validates uploads. Non-automotive images are described in plain language and skipped. Multi-image uploads are accepted only when they appear to be different views or detail shots of the same vehicle/object, so repeated views can be consolidated into a unique BOM.

The analysis response also includes:

- `cost_sheet`: matched warehouse part, SKU, quantity, unit cost, row total, consumables, fitment notes, and grand total
- `token_usage`: token-consuming analysis steps, model name, purpose, input tokens, output tokens, and total tokens

## Run On A New Laptop

Prerequisites:

- Podman and `podman compose`
- Node.js 20+ only if running the frontend outside containers
- Python 3.12+ only if running the backend outside containers
- OpenAI API key only for real Vision LLM mode. Without it, the app runs in demo fallback mode.

Setup:

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set `OPENAI_API_KEY` if you have API billing enabled. Leave it blank for demo mode.

Cost sheets default to INR:

```bash
COST_CURRENCY=INR
USD_TO_INR_RATE=83.0
```

Update `USD_TO_INR_RATE` when you want to use a different conversion rate.

Run the full stack:


```bash
npm run app:restart
```

The full stack runs:

- Dashboard: `http://localhost:5174`
- API: `http://localhost:8000`
- PostgreSQL/pgvector: `localhost:5433`

Check the app status:

```bash
npm run app:status
```

For day-to-day use, prefer the `app:*` commands. They hide noisy Podman Compose container ids and show the app as one frontend, one backend, and one database.

Backend startup runs Alembic migrations automatically before seeding synthetic warehouse data.

Stop everything:

```bash
npm run app:down
```

Reset database and uploaded files:

```bash
podman compose down -v
```

## Local Development Without Containers

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Run migrations manually when needed:

```bash
cd backend
alembic upgrade head
alembic revision -m "describe schema change"
```

Frontend:

```bash
npm run install:frontend
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`.

## What Not To Commit

The `.gitignore` excludes secrets, dependency folders, build output, runtime uploads/crops, caches, and logs. Keep these files committed because they are needed on another laptop:

- `backend/.env.example`
- `backend/requirements.txt`
- `frontend/package.json` and `frontend/package-lock.json`
- `docker-compose.yml`
- `frontend/Containerfile` and `backend/Containerfile`
- `frontend/src/`, `backend/app/`, and `README.md`

## Real Vision LLM Mode

Set `OPENAI_API_KEY` in `backend/.env`. You can also override:

```bash
VISION_MODEL=gpt-5.1
EMBEDDING_MODEL=text-embedding-3-small
```

The detector asks the model for all visible parts, including part name, material, condition, visible part number/OCR text, confidence, and normalized bounding box coordinates. Crops are generated from those bounding boxes.

If the OpenAI API returns an account, quota, or rate-limit error, the backend falls back to demo detections and local deterministic embeddings so the dashboard and database workflow still run. Add billing/quota in the OpenAI platform to enable real Vision LLM mode.

## Next Milestones

- Add SAM/YOLO segmentation masks for precise outlines after LLM region proposals
- Move the orchestrator to async background jobs with queues and progress events
- Connect vendor catalogs and internal part knowledge bases
- Generate BOM cost sheets with fasteners, consumables, oils, grease, clips, and washers
