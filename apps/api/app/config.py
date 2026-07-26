"""Application settings.

Defaults to a local SQLite database so the MVP runs with zero external
dependencies. Switch ``DATABASE_URL`` to a Postgres/pgvector DSN once the
RAG phase (see ``infra/docker-compose.yml``) is introduced.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# opencode Zen/Go share one API key; only the base URL differs.
OPENCODE_BASE_URLS: dict[str, str] = {
    "zen": "https://opencode.ai/zen/v1",
    "go": "https://opencode.ai/zen/go/v1",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore", populate_by_name=True
    )

    app_name: str = "Multi-Agent Change Factory"
    database_url: str = "sqlite:///./agentplatform.db"
    # CORS origins for the Vite dev server.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Max opencode develop -> test -> fix iterations (plan: 2-3).
    max_develop_iterations: int = 3

    # --- opencode runner (Implementation Agent) ---
    # Oriented to the opencode Zen (pay-per-use) or Go ($/mo subscription) plans,
    # which share the OPENCODE_API_KEY credential and differ only by base URL.
    opencode_enabled: bool = True
    opencode_plan: Literal["zen", "go"] = Field(
        default="zen",
        validation_alias=AliasChoices("APP_OPENCODE_PLAN", "OPENCODE_PLAN"),
    )
    opencode_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("APP_OPENCODE_API_KEY", "OPENCODE_API_KEY"),
    )
    opencode_model: str = Field(
        default="opencode/qwen3-coder",
        validation_alias=AliasChoices("APP_OPENCODE_MODEL", "OPENCODE_MODEL"),
    )
    # Per-session wall-clock budget for a headless opencode run.
    opencode_timeout_seconds: int = 900

    @property
    def opencode_base_url(self) -> str:
        return OPENCODE_BASE_URLS[self.opencode_plan]


@lru_cache
def get_settings() -> Settings:
    return Settings()
