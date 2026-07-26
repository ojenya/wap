"""Cost / latency dashboard aggregates."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Viewer
from app.db import get_db
from app.models import RunStatus, StageExecution, WorkflowRun
from app.schemas import MetricsOut, WorkflowRunOut

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("", response_model=MetricsOut)
def get_metrics(_: Viewer, db: Session = Depends(get_db)) -> MetricsOut:
    runs = list(db.scalars(select(WorkflowRun).order_by(WorkflowRun.created_at.desc())))
    completed = [r for r in runs if r.status == RunStatus.completed]
    failed = [r for r in runs if r.status == RunStatus.failed]
    awaiting = [r for r in runs if r.status == RunStatus.awaiting_approval]
    total_tokens = sum(r.total_tokens for r in runs)
    avg_tokens = (total_tokens / len(runs)) if runs else 0.0
    avg_duration = (sum(r.total_duration_ms for r in runs) / len(runs)) if runs else 0.0

    stage_sums: dict[str, list[float]] = defaultdict(list)
    stages = list(db.scalars(select(StageExecution)))
    for s in stages:
        stage_sums[s.name].append(s.duration_ms)
    stage_avg = {k: (sum(v) / len(v) if v else 0.0) for k, v in stage_sums.items()}

    recent = [WorkflowRunOut.model_validate(r) for r in runs[:10]]
    return MetricsOut(
        runs_total=len(runs),
        runs_completed=len(completed),
        runs_failed=len(failed),
        runs_awaiting_approval=len(awaiting),
        avg_tokens=avg_tokens,
        avg_duration_ms=avg_duration,
        total_tokens=total_tokens,
        stage_avg_ms=stage_avg,
        recent_runs=recent,
    )
