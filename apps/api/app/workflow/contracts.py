"""Stage input/output contracts and the shared workflow context."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    source: str
    reference: str
    reason: str = ""


class TaskInput(BaseModel):
    id: str
    title: str
    description: str = ""
    repo_url: str = ""
    base_branch: str = "main"
    task_type: str = "bug_fix"
    repository_id: str | None = None
    path_filters: list[str] = Field(default_factory=list)
    require_approval: bool = True


class StageOutcome(StrEnum):
    completed = "completed"
    failed = "failed"
    skipped = "skipped"
    awaiting_approval = "awaiting_approval"


class StageResult(BaseModel):
    outcome: StageOutcome = StageOutcome.completed
    output: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    tokens: int = 0
    error: str | None = None


class WorkflowContext(BaseModel):
    task: TaskInput
    run_id: str = ""
    worktree_path: str = ""
    head_sha: str = ""
    workflow_params: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def get(self, stage_name: str) -> dict[str, Any]:
        return self.outputs.get(stage_name, {})
