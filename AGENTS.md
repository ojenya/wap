# AGENTS.md

## Project overview

`wap` is a multi-agent "change factory". Two services make up the MVP:

- `apps/api` — FastAPI orchestrator running a deterministic, versioned workflow
  state graph (`apps/api/app/workflow/`). Storage is SQLite by default.
- `apps/web` — React + Vite UI (TanStack Query, styled-components,
  react-hook-form + Yup) for creating tasks, running the workflow, and viewing
  the traced stage timeline + report.

Standard commands live in `README.md` (per-service lint/typecheck/test/build/run)
and in the `scripts` of the root `package.json`. Don't duplicate them here.

## Cursor Cloud specific instructions

- Two dev servers must both run for the UI to work; start them (they are not
  started by the update script):
  - API: `cd apps/api && .venv/bin/uvicorn app.main:app --reload --port 8000`
  - Web: `pnpm --filter @wap/web dev` (Vite on `5173`, proxies `/api` + `/health`
    to `8000` — see `apps/web/vite.config.ts`). Start the API first.
- The Python venv lives at `apps/api/.venv`. Always invoke backend tools via
  `.venv/bin/<tool>` (ruff/mypy/pytest/uvicorn); there is no global install.
- The web `build` script runs `tsc --noEmit && vite build`, so a type error
  fails the build. Run `pnpm --filter @wap/web typecheck` to isolate type issues.
- pnpm blocks package build scripts by default; `esbuild` (needed by Vite) is
  allow-listed via `pnpm.onlyBuiltDependencies` in the root `package.json`. If
  Vite fails to start with an esbuild error, run `pnpm install` again.
- The workflow is intentionally deterministic and needs NO API keys/LLM/network:
  every agent in `apps/api/app/workflow/stages.py` is a rule-based stub with a
  `# EXTENSION POINT` comment marking where a real LLM/RAG/opencode/Playwright
  implementation plugs in. Keep new real integrations behind those seams.
- SQLite file `apps/api/agentplatform.db` is created on first run and is
  gitignored; delete it to reset local state. For the RAG phase, start
  `infra/docker-compose.yml` and set `APP_DATABASE_URL` to the Postgres DSN.
