"""Stage input/output contracts and the shared workflow context.

Every stage declares an explicit contract: it reads from and writes to a
``WorkflowContext`` blackboard, returns a ``StageResult`` with a status,
structured output, cited evidence and a (mock) token cost. This mirrors the
plan's requirement that every decision be traceable.
"""

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
    # Structured outputs keyed by stage name, so later stages can read earlier ones.
    outputs: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def get(self, stage_name: str) -> dict[str, Any]:
        return self.outputs.get(stage_name, {})
