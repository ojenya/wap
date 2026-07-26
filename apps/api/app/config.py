"""Application settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    data_dir: str = "./data"
    secret_key: str = "dev-only-change-me"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_develop_iterations: int = 3

    # Auth / RBAC. When empty, API runs in open-dev mode (single implicit admin).
    auth_required: bool = False
    bootstrap_admin_key: str = Field(
        default="dev-admin-key",
        validation_alias=AliasChoices("APP_BOOTSTRAP_ADMIN_KEY", "BOOTSTRAP_ADMIN_KEY"),
    )
    default_rate_limit_per_minute: int = 120

    # GitLab OAuth / API
    gitlab_base_url: str = Field(
        default="https://gitlab.com",
        validation_alias=AliasChoices("APP_GITLAB_BASE_URL", "GITLAB_BASE_URL"),
    )
    gitlab_oauth_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("APP_GITLAB_OAUTH_CLIENT_ID", "GITLAB_OAUTH_CLIENT_ID"),
    )
    gitlab_oauth_client_secret: str = Field(
        default="",
        validation_alias=AliasChoices(
            "APP_GITLAB_OAUTH_CLIENT_SECRET", "GITLAB_OAUTH_CLIENT_SECRET"
        ),
    )
    gitlab_oauth_redirect_uri: str = Field(
        default="http://localhost:5173/repositories?oauth=gitlab",
        validation_alias=AliasChoices(
            "APP_GITLAB_OAUTH_REDIRECT_URI", "GITLAB_OAUTH_REDIRECT_URI"
        ),
    )

    # opencode Zen / Go
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
    opencode_timeout_seconds: int = 900

    # Playwright sandbox
    playwright_enabled: bool = True
    playwright_timeout_seconds: int = 120

    @property
    def opencode_base_url(self) -> str:
        return OPENCODE_BASE_URLS[self.opencode_plan]


@lru_cache
def get_settings() -> Settings:
    return Settings()
