"""Pydantic request/response schemas for the REST API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RepositoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=8, max_length=500)
    default_branch: str = "main"
    # Personal access token / deploy token. Optional for public repos.
    token: str = ""
    provider: str | None = None  # auto-detected from URL when omitted


class RepositoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    url: str
    provider: str
    default_branch: str
    status: str
    last_error: str | None
    last_synced_at: datetime | None
    head_sha: str | None
    created_at: datetime
    has_token: bool = False


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    repository_id: str | None = None
    repo_url: str = ""
    base_branch: str = "main"
    # bug_fix | feature | refactor | chore | audit
    task_type: str = "bug_fix"


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    repository_id: str | None
    repo_url: str
    base_branch: str
    task_type: str
    created_at: datetime


class StageExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_index: int
    name: str
    agent_role: str
    status: str
    input_payload: dict
    output_payload: dict
    evidence: list
    tokens: int
    duration_ms: float
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    name: str
    content: str
    created_at: datetime


class WorkflowRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    workflow_version: str
    status: str
    risk_level: str | None
    worktree_path: str | None = None
    created_at: datetime
    finished_at: datetime | None
    total_tokens: int
    stages: list[StageExecutionOut] = []
    artifacts: list[ArtifactOut] = []


class TaskDetailOut(TaskOut):
    runs: list[WorkflowRunOut] = []
