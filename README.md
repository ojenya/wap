# wap — Multi-Agent Change Factory

A multi-agent platform that turns a task (or GitLab MR) into a reviewed,
tested code change through an explicit, traceable workflow: **intake → repository
context (RAG) → audit → analysis → spec → approval gate → develop (opencode) →
static checks → sandbox QA → review → report → learning**.

This repository implements a working platform covering the plan end-to-end:

- deterministic (and now **async**) workflow orchestrator with approval gates,
  develop retry loops, real git worktrees, RAG v1 (FTS5), Playwright sandbox,
  GitLab project browser / MR publishing, learning/evals, workflow safe-params,
  RBAC + rate limits;
- OpenAI-like **shadcn/ui** web app (Dashboard, Tasks, Repositories, Learning,
  Workflow settings).

Cursor Cloud–inspired platform layer (see `docs/PLATFORM_PLAN.md`): **Firecracker
microVM environments** (boot/snapshot/restore/destroy; emulates without KVM),
secrets vault + egress policy, artifact gallery, run transcript, HITL
comments/steer, parallel subagents, automations (webhook/cron), GitHub draft
PRs + GitLab MRs, MCP registry, desktop verification seam. Deterministic stubs
keep the lifecycle runnable without external credentials; real adapters plug in
at the documented seams.

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
- **Frontend:** React 18, TypeScript, Vite 5, TanStack Query, **shadcn/ui**
  (Radix + Tailwind), react-hook-form + Yup. OpenAI-like light UI.

## Getting started

### Backend (`apps/api`)

```bash
cd apps/api
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/playwright install chromium   # product worktree E2E (Sandbox QA)
.venv/bin/uvicorn app.main:app --reload --port 8000   # http://localhost:8000
```

- Lint: `.venv/bin/ruff check .`
- Types: `.venv/bin/mypy app`
- Tests: `.venv/bin/pytest`

Sandbox QA runs Playwright against the **task worktree** (the product under
change), writes `.wap/e2e/` into that tree, and stores artifacts under
`data/artifacts/<run_id>/playwright/`. With default
`playwright_required=true`, a missing worktree/Chromium **fails** the run
instead of skipping — look for stage `mode: worktree-e2e` to confirm E2E ran.

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
proxies `/api` to the `api` service via `API_PROXY_TARGET`. Git mirrors and
per-run worktrees persist under `./data` (mounted into the API container).
For the RAG phase, start Postgres + pgvector with `docker compose --profile rag up`.

## OAuth (GitLab / GitHub) — recommended

Create an OAuth application and set env vars (also wired in `docker-compose.yml`):

**GitLab** (User Settings → Applications, or Group/Instance apps):
- Redirect URI: `http://localhost:5173/repositories?oauth=gitlab`
- Scopes: `api`, `read_repository`, `write_repository`
- Env: `GITLAB_OAUTH_CLIENT_ID`, `GITLAB_OAUTH_CLIENT_SECRET`

**GitHub** (Settings → Developer settings → OAuth Apps):
- Authorization callback URL: `http://localhost:5173/repositories?oauth=github`
- Env: `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`

Then open **Repositories → Connect GitLab / Connect GitHub**. The UI never asks
for a PAT; the access token is stored encrypted and reused for clone/push/MR.

Manual PAT/URL connect remains under “Show manual form” as a fallback.

## Connect a repository (GitLab / GitHub / git)

Use the **Repositories** page in the UI, or the API:

```bash
curl -X POST http://localhost:8000/api/repositories \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "payments-service",
    "url": "https://gitlab.com/org/project.git",
    "default_branch": "main",
    "token": "glpat-..."
  }'
```

Tokens are encrypted at rest (`APP_SECRET_KEY`). Provider is auto-detected from
the URL. On connect the API clones a durable mirror under `APP_DATA_DIR/mirrors/`;
every workflow run then creates an **isolated git worktree** under
`APP_DATA_DIR/worktrees/<run_id>` — this is how audit/develop actually touch code.

- **audit** tasks are read-only (develop stage skipped).
- **feature / bug_fix / …** write into the worktree (real `opencode run` when
  `OPENCODE_API_KEY` is set, otherwise a deterministic stub patch + `git diff`).

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
