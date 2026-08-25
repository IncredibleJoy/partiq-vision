# PartIQ Vision Architecture

PartIQ Vision is a containerized full-stack prototype for vehicle image analysis, part detection, BOM consolidation, warehouse matching, costing, and human review.

## System Context

```mermaid
flowchart LR
  user[Estimator / Reviewer]

  subgraph browser[Browser]
    ui[React + Vite dashboard]
  end

  subgraph api[FastAPI backend]
    routes[API routes]
    orchestrator[OrchestratorAgent]
    agents[Vision, Crop, BOM, Knowledge Search, Reflection agents]
    storage[Mounted storage<br/>uploads + crops]
  end

  subgraph data[PostgreSQL + pgvector]
    jobs[(analysis_jobs)]
    detections[(detections)]
    vectors[(part_vectors)]
    warehouse[(warehouse_parts)]
    warehouseVectors[(warehouse_part_vectors)]
    recs[(recommendations)]
    traces[(agent_traces)]
  end

  openai[OpenAI Responses API<br/>Vision validation + detection]
  embeddings[OpenAI Embeddings API<br/>optional]
  localFallback[Local deterministic fallback<br/>demo detections + token vectors]

  user --> ui
  ui -->|/api/health| routes
  ui -->|/api/analyze multipart images| routes
  ui -->|/api/jobs/:id/refine JSON edits| routes
  ui -->|/storage/crops/*| storage

  routes --> orchestrator
  orchestrator --> agents
  agents --> storage
  agents --> openai
  agents --> localFallback
  routes --> embeddings
  routes --> localFallback

  routes --> jobs
  routes --> detections
  routes --> vectors
  routes --> recs
  routes --> traces
  agents --> warehouse
  agents --> warehouseVectors
  warehouseVectors --> warehouse
```

## Container Deployment

```mermaid
flowchart TB
  subgraph compose[docker-compose.yml]
    frontend[frontend<br/>Containerfile.frontend<br/>Node 23 + Vite<br/>host:5174 -> container:5173]
    backend[backend<br/>backend/Containerfile<br/>Python 3.14 + Uvicorn<br/>host:8000 -> container:8000]
    db[db<br/>pgvector/pgvector:pg17<br/>host:5433 -> container:5432]
    pgvol[(partiq_pgdata)]
    storagevol[(partiq_storage)]
  end

  frontend -->|Vite proxy /api and /storage<br/>VITE_API_PROXY_TARGET=http://backend:8000| backend
  backend -->|DATABASE_URL=postgresql://partiq:partiq@db:5432/partiq| db
  backend -->|uploads and crops| storagevol
  db --> pgvol
```

## Backend Runtime Components

```mermaid
flowchart TD
  main[app/main.py<br/>FastAPI routes, startup, CORS, static files]
  config[config.py<br/>env settings]
  db[db.py<br/>pool + Alembic migrations]
  repo[repository.py<br/>job, detection, trace, recommendation persistence]
  schemas[schemas.py<br/>Pydantic API contracts]

  orchestrator[agents.py<br/>OrchestratorAgent]
  validation[vision.py<br/>validate_image_set]
  vision[vision.py<br/>analyze_image]
  crop[images.py<br/>save_upload + create_crop]
  bom[bom.py<br/>consolidate_bom]
  costing[costing.py<br/>build_cost_sheet]
  knowledge[agents.py<br/>KnowledgeSearchAgent]
  reflection[agents.py<br/>ReflectionAgent]
  vectors[vector_store.py<br/>embedding + detection vector index]
  warehouse[warehouse.py<br/>seed, list, summary, semantic search]

  main --> config
  main --> db
  main --> repo
  main --> schemas
  main --> orchestrator
  main --> vectors
  main --> warehouse

  orchestrator --> crop
  orchestrator --> validation
  orchestrator --> vision
  orchestrator --> bom
  orchestrator --> costing
  orchestrator --> knowledge
  orchestrator --> reflection

  knowledge --> warehouse
  costing --> warehouse
  vectors --> db
  warehouse --> db
  repo --> db
```

## Image Analysis Flow

```mermaid
sequenceDiagram
  actor User
  participant UI as React dashboard
  participant API as FastAPI /api/analyze
  participant Orch as OrchestratorAgent
  participant Vision as Vision/OpenAI or demo
  participant Files as storage/uploads + crops
  participant BOM as BOM + Costing
  participant WH as Warehouse pgvector search
  participant DB as PostgreSQL

  User->>UI: Select one or more vehicle images
  UI->>API: POST /api/analyze multipart/form-data
  API->>Orch: run(files)
  Orch->>Files: save_upload for each image
  Orch->>Vision: validate_image_set(images)
  alt accepted automotive same-object upload
    loop each image
      Orch->>Vision: analyze_image(image)
      Vision-->>Orch: detections, context, token usage
      Orch->>Files: create_crop per bounding box
    end
    Orch->>BOM: consolidate_bom(detections)
    BOM->>WH: search_warehouse_parts for cost matches
    Orch->>WH: recommend_from_database
    Orch->>Orch: ReflectionAgent verifies BOM completeness
    API->>DB: save_job(job, detections, recommendations, traces)
    API->>DB: save_detection_vectors
    API-->>UI: JobResponse
  else rejected or validation error
    API-->>UI: JobResponse with message and empty BOM
  end
```

## Human Review And Refinement Flow

```mermaid
sequenceDiagram
  actor User
  participant UI as React dashboard
  participant API as FastAPI /api/jobs/:id/refine
  participant Repo as repository.py
  participant BOM as BOM + Costing
  participant Agents as KnowledgeSearchAgent + ReflectionAgent
  participant DB as PostgreSQL + pgvector

  User->>UI: Edit detection labels, material, condition, OCR, notes
  UI->>API: POST /api/jobs/{job_id}/refine
  API->>Repo: update_detection_labels
  Repo->>DB: update detections, clear old recommendations, add trace
  API->>Repo: get_job
  API->>BOM: recompute BOM and cost sheet
  API->>Agents: rerun recommendations and reflection
  API->>DB: replace_recommendations
  API->>DB: save_detection_vectors
  API-->>UI: refreshed JobResponse
```

## Data Model

```mermaid
erDiagram
  analysis_jobs ||--o{ detections : contains
  analysis_jobs ||--o{ part_vectors : indexes
  analysis_jobs ||--o{ recommendations : produces
  analysis_jobs ||--o{ agent_traces : records
  detections ||--|| part_vectors : embeds
  warehouse_parts ||--|| warehouse_part_vectors : embeds

  analysis_jobs {
    uuid id PK
    timestamptz created_at
    text model_mode
    text vehicle_context
    jsonb token_usage
  }

  detections {
    uuid id PK
    uuid job_id FK
    text source_image
    text part_name
    text category
    text material
    text condition
    text visible_part_no
    text minute_details
    double confidence
    jsonb bbox
    text crop_url
  }

  part_vectors {
    uuid detection_id PK
    uuid job_id FK
    text content
    vector embedding
  }

  recommendations {
    uuid id PK
    uuid job_id FK
    text part_name
    text reason
    text recommendation_type
    double confidence
    jsonb related_parts
  }

  agent_traces {
    bigint id PK
    uuid job_id FK
    text agent
    text action
    text status
    text detail
    timestamptz created_at
  }

  warehouse_parts {
    text sku PK
    text part_name
    text category
    text vehicle_system
    text material
    numeric unit_cost
    text currency
    integer stock_quantity
    text supplier
    text cluster_key
    jsonb aliases
    jsonb visible_part_nos
    text embedding_content
  }

  warehouse_part_vectors {
    text sku PK
    vector embedding
    timestamptz updated_at
  }
```

## API Surface

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Reports backend, PostgreSQL/pgvector, and OpenAI connectivity. |
| `POST /api/analyze` | Uploads images, runs the agent pipeline, persists the job, and returns detections, BOM, cost sheet, recommendations, token usage, and trace. |
| `GET /api/jobs/{job_id}` | Reloads a persisted job and recomputes BOM/cost sheet from saved detections. |
| `POST /api/jobs/{job_id}/refine` | Applies human label edits, recomputes BOM/cost sheet, reruns recommendations, and refreshes vectors. |
| `GET /api/search?q=...` | Searches previously indexed detected parts using `part_vectors`. |
| `GET /api/warehouse/summary` | Returns seeded warehouse inventory summary. |
| `GET /api/warehouse/parts` | Lists warehouse catalog rows. |
| `GET /api/warehouse/search?q=...` | Searches synthetic warehouse stock using vector and lexical matching. |
| `WS /ws/screener` | Echo-style websocket placeholder for future screening/progress workflows. |

## Key Design Notes

- The frontend uses the Vite dev server as a proxy for `/api` and `/storage`, so browser requests can stay same-origin during development and in the frontend container.
- Backend startup creates storage directories, runs Alembic migrations, opens the PostgreSQL pool, and seeds the synthetic warehouse catalog.
- OpenAI is optional. Without `OPENAI_API_KEY`, validation accepts demo uploads, vision returns deterministic demo detections, and embeddings use local token-cluster vectors.
- Uploaded originals and generated crops live in mounted storage, while normalized detections, traces, recommendations, token usage, warehouse rows, and vectors live in PostgreSQL.
- Costing is generated from BOM rows by querying the warehouse and converting USD warehouse costs to the configured display currency, INR by default.
