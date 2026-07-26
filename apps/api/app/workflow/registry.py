"""Versioned workflow definitions.

The core lifecycle is hardcoded for reproducibility and compliance. Definitions
are keyed by version so future edits are additive rather than mutating history
(the plan's "versioned workflow definitions" requirement). A future UI can
render these as a read-only graph.
"""

from __future__ import annotations

from app.workflow.base import Stage
from app.workflow.stages import (
    AnalysisStage,
    ApprovalGateStage,
    AuditStage,
    DevelopStage,
    IntakeStage,
    LearningStage,
    ReportStage,
    RepositoryContextStage,
    ReviewStage,
    SandboxQAStage,
    SpecStage,
    StaticChecksStage,
)

WORKFLOWS: dict[str, list[type[Stage]]] = {
    "core-v1": [
        IntakeStage,
        RepositoryContextStage,
        AuditStage,
        AnalysisStage,
        SpecStage,
        ApprovalGateStage,
        DevelopStage,
        StaticChecksStage,
        SandboxQAStage,
        ReviewStage,
        ReportStage,
        LearningStage,
    ],
}

DEFAULT_WORKFLOW = "core-v1"


def build_workflow(version: str = DEFAULT_WORKFLOW) -> list[Stage]:
    if version not in WORKFLOWS:
        raise KeyError(f"Unknown workflow version: {version}")
    return [stage_cls() for stage_cls in WORKFLOWS[version]]
