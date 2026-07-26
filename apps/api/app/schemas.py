"""Pydantic request/response schemas for the REST API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = ""
    repo_url: str = ""
    base_branch: str = "main"
    task_type: str = "bug_fix"


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
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
    created_at: datetime
    finished_at: datetime | None
    total_tokens: int
    stages: list[StageExecutionOut] = []
    artifacts: list[ArtifactOut] = []


class TaskDetailOut(TaskOut):
    runs: list[WorkflowRunOut] = []
