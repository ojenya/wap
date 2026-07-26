# wap — Multi-Agent Change Factory

A multi-agent platform that turns a task (or GitLab MR) into a reviewed,
tested code change through an explicit, traceable workflow: **intake → repository
context (RAG) → audit → analysis → spec → approval gate → develop (opencode) →
static checks → sandbox QA → review → report → learning**.

This repository implements the **MVP foundation** (phases 1–2 of the plan):

- a **deterministic workflow orchestrator** that runs the full lifecycle as a
  versioned state graph and persists a complete trace of every stage, and
- a **web UI** to create tasks, run the workflow, and inspect the stage timeline
  and final report.

Advanced phases (real LLM gateway, pgvector RAG, isolated `opencode` runner,
Playwright sandbox, GitLab integration, learning loop) are wired as clearly
isolated extension points (`# EXTENSION POINT` in `apps/api/app/workflow/stages.py`)
backed by deterministic stub agents, so the whole lifecycle runs end-to-end with
zero external credentials.

## Monorepo layout

| Path | What |
| --- | --- |
| `apps/api` | FastAPI orchestrator: task model, workflow engine, REST API (Python) |
| `apps/web` | React + Vite UI (TanStack Query, styled-components, react-hook-form + Yup) |
| `packages/shared` | Shared TypeScript domain contracts |
| `infra` | Optional `docker-compose.yml` (Postgres + pgvector) for the RAG phase |

## Tech stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2. Storage is
  SQLite by default; switch `APP_DATABASE_URL` to Postgres/pgvector for RAG.
- **Frontend:** React 18, TypeScript, Vite 5, TanStack Query, styled-components,
  react-hook-form + Yup.

## Getting started

### Backend (`apps/api`)

```bash
cd apps/api
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload --port 8000   # http://localhost:8000
```

- Lint: `.venv/bin/ruff check .`
- Types: `.venv/bin/mypy app`
- Tests: `.venv/bin/pytest`

### Frontend (`apps/web`)

```bash
pnpm install                 # from the repo root
pnpm --filter @wap/web dev   # http://localhost:5173 (proxies /api to :8000)
```

- Lint: `pnpm --filter @wap/web lint`
- Types: `pnpm --filter @wap/web typecheck`
- Build: `pnpm --filter @wap/web build`

Start the backend first, then the frontend, and open http://localhost:5173.

### Run from Docker

Run the whole platform in containers (no local Python/Node/pnpm needed):

```bash
docker compose up --build      # web -> http://localhost:5173, api -> http://localhost:8000
```

Sources are mounted for hot reload (`uvicorn --reload`, Vite). The web container
proxies `/api` to the `api` service via `API_PROXY_TARGET`. For the RAG phase,
start Postgres + pgvector with `docker compose --profile rag up`.

## opencode integration (Zen / Go)

The Implementation Agent delegates code changes to the terminal-native
[`opencode`](https://opencode.ai) CLI (installed in the API image), oriented to
the **opencode Zen** (pay-per-use) or **opencode Go** (subscription) plans. Both
share one credential and differ only by base URL:

| Plan | `OPENCODE_PLAN` | Base URL |
| --- | --- | --- |
| Zen | `zen` (default) | `https://opencode.ai/zen/v1` |
| Go | `go` | `https://opencode.ai/zen/go/v1` |

Enable it by exporting env vars before starting the API (or `docker compose up`):

```bash
export OPENCODE_API_KEY=...          # from https://opencode.ai/auth
export OPENCODE_PLAN=zen             # or "go"
export OPENCODE_MODEL=opencode/qwen3-coder
```

When `OPENCODE_API_KEY` and the `opencode` CLI are both present, the `develop`
stage runs a real headless `opencode run` session; otherwise it transparently
falls back to a deterministic stub so the workflow always completes. The active
mode/plan/model is recorded in the `develop` stage's `runner` output.
