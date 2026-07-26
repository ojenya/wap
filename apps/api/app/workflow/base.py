"""Base ``Stage`` abstraction.

A stage is a single agent role in the lifecycle. Real implementations (LLM-,
RAG- or opencode-backed) can subclass ``Stage`` and be dropped into the
workflow definition without changing the engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.workflow.contracts import StageResult, WorkflowContext


class Stage(ABC):
    #: Stable stage identifier used as the blackboard key and in traces.
    name: str = "stage"
    #: Human-readable agent role.
    agent_role: str = "Agent"

    @abstractmethod
    def run(self, context: WorkflowContext) -> StageResult:
        """Execute the stage against the shared context and return a result."""
        raise NotImplementedError
