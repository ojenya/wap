# Platform plan — Cursor Cloud–inspired Change Factory

Goal: evolve `wap` from a serial orchestrator MVP into an operable cloud-agent
platform with environment fidelity, proof artifacts, secrets/egress, HITL
steering, parallelism, automations, dual SCM, MCP tools, and desktop verification.

## Feature matrix

| # | Feature | Module(s) | Acceptance |
| --- | --- | --- | --- |
| 1 | Environment snapshots + update scripts | `environments`, `Environment` model | CRUD env; refresh runs update script; bind to repo |
| 2 | Secrets vault + egress policy | `secrets_vault`, `VaultSecret`, `EgressPolicy` | encrypt-at-rest; never leak plaintext; domain allowlist check |
| 3 | Artifact gallery + download | `routers/artifacts` | list/download binary artifacts; UI gallery |
| 4 | Run transcript / events | `events`, `RunEvent` | stage/tool events persisted; API timeline |
| 5 | HITL comments + steer | `routers/hitl`, `RunComment` | comment, approve note, continue-with-guidance |
| 6 | Parallel subagents | `workflow/parallel` | fan-out explore/fix/test; merge into analysis |
| 7 | Automations | `routers/automations` | webhook/cron/gitlab_mr triggers → task+run |
| 8 | GitHub PR last-mile | `github_client` | draft PR + body with artifact summary |
| 9 | MCP tool registry | `mcp_registry` | register/list/invoke (stdio/http stub + contract) |
| 10 | Computer-use verification | `computer_use` | desktop session seam after Playwright |

## Non-goals (this iteration)
- Full MCP OAuth broker
- Production cron scheduler daemon (API-trigger + due-scan only)

## Firecracker environments (added)
- Backends: `firecracker` (preferred) | `local`
- Modes: `APP_FIRECRACKER_MODE=auto|emulate|require|local`
- Lifecycle API: boot / snapshot / restore / destroy / exec
- Workflow boots a VM for repo-bound Environments and runs stages against
  `vm.workspace_path`; snapshots after the run when enabled
- Without `/dev/kvm` + kernel/rootfs, `auto`/`emulate` still exercise the
  Firecracker API lifecycle for CI and local agents

## Testing strategy
- Unit/integration: every new router + service via pytest
- Workflow: events emitted, parallel merge, GitHub publish path
- Web: vitest for API client helpers + critical page render contracts
- Strict Playwright remains required when opted in
