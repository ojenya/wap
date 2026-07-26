"""Multi-agent change-factory orchestrator API.

MVP scope: Foundation (task model, storage, API) + Deterministic Workflow
(explicit intake -> audit -> analysis -> spec -> develop -> static checks ->
sandbox -> review -> report -> learn state graph).

Advanced phases (real LLM gateway, RAG/pgvector, opencode runner, Playwright
sandbox, GitLab integration, learning loop) are wired as clearly isolated
extension points backed by deterministic stub adapters so the whole lifecycle
runs end-to-end without external credentials.
"""

__version__ = "0.1.0"
