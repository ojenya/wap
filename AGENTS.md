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
- The workflow is intentionally deterministic without API keys. Stages in
  `apps/api/app/workflow/stages.py` are rule-based stubs with `# EXTENSION POINT`
  seams — except **git worktrees are real**: when a Task has `repository_id`,
  the engine clones/fetches a mirror and creates
  `APP_DATA_DIR/worktrees/<run_id>` before stages run. Develop writes a stub
  patch into that worktree (or a real `opencode run` if configured).
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
  opencode Zen/Go plans; it activates when `OPENCODE_API_KEY` is set AND the
  `opencode` CLI is on PATH (baked into the API image at `/root/.opencode/bin`)
  AND a worktree path is available. Otherwise Develop falls back to a
  worktree-stub (real `git diff`) or a synthetic stub (no repo attached).
- UI is OpenAI-like via **shadcn/ui** (Radix + Tailwind + CVA). Components live
  under `apps/web/src/components/ui/` (copied into the repo — no runtime dependency
  on a shadcn registry). Prefer extending those primitives over reintroducing
  styled-components.
- Connected repos: prefer OAuth via `/api/oauth/{gitlab|github}/start` +
  callback (Repositories page buttons). Tokens land in `oauth_connections`
  encrypted; connecting a remote repo copies the token onto `repositories`.
  Manual `POST /api/repositories` + PAT still works. For a local path when the
  API runs in Docker, use the container path under the mounted volume
  (e.g. `/app/data/demo-origin`), not the host `/workspace/...`.
- Runs are **async by default** (`POST /api/tasks/{id}/runs`); use `?sync=true`
  in tests. High-risk tasks pause at `awaiting_approval` until
  `POST /api/runs/{id}/approve`. Stop with `POST /api/runs/{id}/cancel`
  (status `cancelled`; cooperative — current stage may finish, later stages
  skip). UI: Task detail **Stop run** + timeline transcript. Polls every 1.5s.
- Auth: `APP_AUTH_REQUIRED=false` (default) is open-dev mode with rate limits.
  Set `true` + `X-API-Key` (`APP_BOOTSTRAP_ADMIN_KEY`) for RBAC.
- Safe workflow knobs live in `/api/workflow-config` (and Workflow page) — only
  allowlisted keys, never arbitrary graph edits.
- Learning: `/api/learning/cases` + `POST /api/learning/evals/run`. Metrics:
  `/api/metrics`.
- Sandbox QA Playwright E2E targets the **product worktree** (software under
  development), not the platform UI. `SandboxQAStage` starts the app from the
  worktree, generates `.wap/e2e/` there, and stores screenshot/video/trace under
  `APP_DATA_DIR/artifacts/<run_id>/playwright/`.
- **No silent skips in production defaults:** workflow param
  `playwright_required=true` (default) makes any non-`worktree-e2e` outcome
  fail the stage/run. To be sure E2E actually ran, check the stage output
  `mode === "worktree-e2e"` and `all_passed === true`, plus artifacts under
  `data/artifacts/<run_id>/playwright/`. Prerequisites: task has
  `repository_id` (real worktree), Chromium via
  `apps/api/.venv/bin/playwright install chromium` (Docker image installs at
  build), and `playwright_enabled=true`. Set `playwright_required=false` only
  for local smoke runs without a product checkout.
- Platform plan (Cursor Cloud–inspired): `docs/PLATFORM_PLAN.md`. New surfaces:
  Environments (`/api/environments`), Secrets+Egress (`/api/secrets`,
  `/api/egress-policy`), Artifacts download (`/api/artifacts/{id}/content`),
  HITL transcript (`/api/runs/{id}/events|comments|steer`), Automations
  (`/api/automations`), MCP (`/api/mcp`), GitHub draft PRs, parallel subagents
  in analysis, desktop verification session on sandbox_qa.
- **Firecracker VMs:** `app/vm/` — capabilities at
  `GET /api/environments/capabilities`. Lifecycle:
  `.../vms/boot|snapshot|restore|destroy|exec|screenshot` and
  `DELETE /api/environments/{id}` (UI Delete button). Set
  `APP_FIRECRACKER_MODE=emulate` in CI (default `auto` emulates when KVM/assets
  missing). For real microVMs on a KVM host: install `firecracker`, set
  `APP_FIRECRACKER_KERNEL` + `APP_FIRECRACKER_ROOTFS`, mode `auto`/`require`.
  Repo-linked Environments boot a VM per run; stages use `vm.workspace_path`.
  `data/vms/<id>/` is the instance disk/socket (not screenshots). Manual VM
  screenshots go to `data/artifacts/vms/<id>/` via Environments → Screenshot;
  product E2E shots stay under `data/artifacts/<run_id>/playwright/`.
- Web pages: Environments + Automations in the sidebar; Task detail shows
  transcript, HITL panel, artifact gallery, desktop instructions.
