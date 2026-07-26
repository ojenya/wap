"""Workflow engine: runs the stage graph and persists a full trace.

Executes stages sequentially, recording each stage's structured input/output,
status, duration and token cost as ``StageExecution`` rows, and emitting
report/patch artifacts. If a stage fails, the run is marked failed and
remaining stages are skipped.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import (
    Artifact,
    RiskLevel,
    RunStatus,
    StageExecution,
    StageStatus,
    Task,
    WorkflowRun,
)
from app.workflow.contracts import StageOutcome, TaskInput, WorkflowContext
from app.workflow.registry import DEFAULT_WORKFLOW, build_workflow


def _now() -> datetime:
    return datetime.now(UTC)


def run_workflow(db: Session, task: Task, version: str = DEFAULT_WORKFLOW) -> WorkflowRun:
    """Execute the workflow for ``task`` and persist a fully-traced run."""
    run = WorkflowRun(task_id=task.id, workflow_version=version, status=RunStatus.running)
    db.add(run)
    db.commit()
    db.refresh(run)

    context = WorkflowContext(
        task=TaskInput(
            id=task.id,
            title=task.title,
            description=task.description,
            repo_url=task.repo_url,
            base_branch=task.base_branch,
            task_type=task.task_type,
        )
    )

    stages = build_workflow(version)
    failed = False

    for index, stage in enumerate(stages):
        execution = StageExecution(
            run_id=run.id,
            order_index=index,
            name=stage.name,
            agent_role=stage.agent_role,
        )

        if failed:
            execution.status = StageStatus.skipped
            db.add(execution)
            continue

        execution.status = StageStatus.running
        execution.started_at = _now()
        execution.input_payload = context.model_dump(mode="json")
        db.add(execution)
        db.commit()

        start = time.perf_counter()
        try:
            result = stage.run(context)
        except Exception as exc:  # noqa: BLE001 - record and stop the run
            execution.status = StageStatus.failed
            execution.error = str(exc)
            execution.finished_at = _now()
            execution.duration_ms = (time.perf_counter() - start) * 1000
            db.commit()
            failed = True
            continue

        execution.duration_ms = (time.perf_counter() - start) * 1000
        execution.finished_at = _now()
        execution.output_payload = result.output
        execution.evidence = [e.model_dump() for e in result.evidence]
        execution.tokens = result.tokens
        run.total_tokens += result.tokens

        if result.outcome == StageOutcome.failed:
            execution.status = StageStatus.failed
            execution.error = result.error
            failed = True
        else:
            execution.status = StageStatus.completed
            context.outputs[stage.name] = result.output
            _capture_artifacts(db, run, stage.name, result.output)

        db.commit()

    intake = context.outputs.get("intake", {})
    if intake.get("risk_level"):
        run.risk_level = RiskLevel(intake["risk_level"])
    run.status = RunStatus.failed if failed else RunStatus.completed
    run.finished_at = _now()
    db.commit()
    db.refresh(run)
    return run


def _capture_artifacts(db: Session, run: WorkflowRun, stage_name: str, output: dict) -> None:
    if stage_name == "report" and output.get("report_markdown"):
        db.add(Artifact(run_id=run.id, kind="report", name="final-report.md",
                        content=output["report_markdown"]))
    if stage_name == "develop" and output.get("diff"):
        db.add(Artifact(run_id=run.id, kind="patch", name="change.patch",
                        content=output["diff"]))
