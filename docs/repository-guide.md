# PartIQ Vision repository guide

| Path | Purpose |
|---|---|
| `backend/app/` | FastAPI service and agent workflow |
| `backend/alembic/` | Database migrations |
| `backend/prompts/` | Agent and recommendation prompts |
| `frontend/src/` | React interface |
| `docs/` | Architecture, prompt guidance and development documentation |
| `scripts/` | Container build, startup, restart and status commands |
| `output/` | Ignored generated artifacts |
| `.github/workflows/` | Repository checks |

The backend/frontend separation is retained. Use the root `package.json` scripts to build or control the container application; setup and environment instructions remain in the main README.

CI checks Python 3.12 source compilation and builds the frontend from its lockfile. It does not run the database or paid vision calls. The obsolete Python 2.7–3.8 workflow and nonexistent root requirements path were replaced.
