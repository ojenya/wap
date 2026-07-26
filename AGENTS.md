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
- Docker run mode: `docker compose up --build` (root `docker-compose.yml`) runs
  `api` (:8000) + `web` (:5173). It binds the same host ports as the local dev
  servers, so stop the local tmux `api-dev`/`web-dev` sessions before `up` to
  avoid port conflicts. Sources are bind-mounted for hot reload; a dependency
  change requires a rebuild (`docker compose build`). Docker is NOT preinstalled
  on the base VM — install it (with the DinD `fuse-overlayfs` + `iptables-legacy`
  workarounds) only when you actually need containers.
- opencode runner (`apps/api/app/workflow/opencode_runner.py`) is oriented to the
  opencode Zen/Go plans; it only activates when `OPENCODE_API_KEY` is set AND the
  `opencode` CLI is on PATH (baked into the API image at `/root/.opencode/bin`).
  Otherwise `DevelopStage` falls back to the deterministic stub, so tests and the
  no-key path stay reproducible. The runner's real coding session also needs an
  isolated worktree path (`OpencodeRequest.workdir`) — currently `None` (the next
  extension point).
