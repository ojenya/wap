"""Stage input/output contracts and the shared workflow context."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """A citation backing a stage's decision (retrieved file, test, prior MR...)."""

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


class StageOutcome(StrEnum):
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class StageResult(BaseModel):
    outcome: StageOutcome = StageOutcome.completed
    output: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    tokens: int = 0
    error: str | None = None


class WorkflowContext(BaseModel):
    """Blackboard shared across stages during a single run."""

    task: TaskInput
    # Absolute path to the per-run git worktree (set by the engine when a
    # connected repository is attached). Empty string means no worktree.
    worktree_path: str = ""
    head_sha: str = ""
    # Structured outputs keyed by stage name.
    outputs: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def get(self, stage_name: str) -> dict[str, Any]:
        return self.outputs.get(stage_name, {})
