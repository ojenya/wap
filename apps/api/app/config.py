"""Application settings.

Defaults to a local SQLite database so the MVP runs with zero external
dependencies. Switch ``DATABASE_URL`` to a Postgres/pgvector DSN once the
RAG phase (see ``infra/docker-compose.yml``) is introduced.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    app_name: str = "Multi-Agent Change Factory"
    database_url: str = "sqlite:///./agentplatform.db"
    # CORS origins for the Vite dev server.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Max opencode develop -> test -> fix iterations (plan: 2-3).
    max_develop_iterations: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
