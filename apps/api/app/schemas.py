"""Pydantic request/response schemas for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RepositoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = Field(min_length=8, max_length=500)
    default_branch: str = "main"
    token: str = ""
    provider: str | None = None
    gitlab_project_id: int | None = None
    path_filters: list[str] = Field(default_factory=list)


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
    gitlab_project_id: int | None = None
    path_filters: list = Field(default_factory=list)


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    repository_id: str | None = None
    repo_url: str = ""
    base_branch: str = "main"
    task_type: str = "bug_fix"
    path_filters: list[str] = Field(default_factory=list)
    require_approval: bool = True


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    repository_id: str | None
    repo_url: str
    base_branch: str
    task_type: str
    path_filters: list = Field(default_factory=list)
    require_approval: bool = True
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
    develop_iterations: int = 0
    approved_by: str | None = None
    mr_url: str | None = None
    created_at: datetime
    finished_at: datetime | None
    total_tokens: int
    total_duration_ms: float = 0.0
    stages: list[StageExecutionOut] = []
    artifacts: list[ArtifactOut] = []


class TaskDetailOut(TaskOut):
    runs: list[WorkflowRunOut] = []


class ApproveIn(BaseModel):
    note: str = ""


class WorkflowConfigOut(BaseModel):
    name: str
    version: str
    params: dict[str, Any]
    updated_at: datetime | None = None
    allowed_keys: list[str] = Field(default_factory=list)


class WorkflowConfigUpdate(BaseModel):
    params: dict[str, Any]


class EvalCaseIn(BaseModel):
    name: str
    task_title: str
    task_description: str = ""
    task_type: str = "bug_fix"
    expect_risk: str | None = None
    expect_status: str = "completed"


class EvalCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    task_title: str
    task_description: str
    task_type: str
    expect_risk: str | None
    expect_status: str
    created_at: datetime


class CaseMemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_type: str
    title: str
    lesson: str
    validated: bool
    run_id: str | None
    repository_id: str | None
    created_at: datetime


class MetricsOut(BaseModel):
    runs_total: int
    runs_completed: int
    runs_failed: int
    runs_awaiting_approval: int
    avg_tokens: float
    avg_duration_ms: float
    total_tokens: int
    stage_avg_ms: dict[str, float]
    recent_runs: list[WorkflowRunOut]
