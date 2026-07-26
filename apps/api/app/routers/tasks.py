"""Task and workflow-run endpoints (async by default)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Operator, Viewer
from app.db import get_db
from app.models import Repository, Task, WorkflowRun
from app.schemas import ApproveIn, TaskCreate, TaskDetailOut, TaskOut, WorkflowRunOut
from app.workflow.engine import approve_run, run_workflow, start_workflow_async
from app.workflow.registry import WORKFLOWS

router = APIRouter(prefix="/api", tags=["tasks"])


@router.get("/workflows")
def list_workflows(_: Viewer) -> dict[str, list[str]]:
    return {
        version: [stage_cls.name for stage_cls in stages]
        for version, stages in WORKFLOWS.items()
    }


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, _: Operator, db: Session = Depends(get_db)) -> Task:
    data = payload.model_dump()
    if data.get("repository_id"):
        repo = db.get(Repository, data["repository_id"])
        if repo is None:
            raise HTTPException(status_code=404, detail="Repository not found")
        data["repo_url"] = data["repo_url"] or repo.url
        data["base_branch"] = data["base_branch"] or repo.default_branch
    task = Task(**data)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(_: Viewer, db: Session = Depends(get_db)) -> list[Task]:
    return list(db.scalars(select(Task).order_by(Task.created_at.desc())))


@router.get("/tasks/{task_id}", response_model=TaskDetailOut)
def get_task(task_id: str, _: Viewer, db: Session = Depends(get_db)) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks/{task_id}/runs", response_model=WorkflowRunOut, status_code=201)
def start_run(
    task_id: str,
    _: Operator,
    db: Session = Depends(get_db),
    sync: bool = Query(False, description="Run synchronously (tests / short demos)"),
) -> WorkflowRun:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if sync:
        return run_workflow(db, task)

    run_id = start_workflow_async(task_id)
    # Brief wait so fast runs often return a meaningful status on first poll.
    run: WorkflowRun | None = None
    for _attempt in range(20):
        db.expire_all()
        run = db.get(WorkflowRun, run_id)
        if run and run.status.value not in {"pending"}:
            return run
        time.sleep(0.05)
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=500, detail="Failed to create run")
    return run


@router.get("/runs/{run_id}", response_model=WorkflowRunOut)
def get_run(run_id: str, _: Viewer, db: Session = Depends(get_db)) -> WorkflowRun:
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/runs/{run_id}/approve", response_model=WorkflowRunOut)
def approve(
    run_id: str,
    payload: ApproveIn,
    principal: Operator,
    db: Session = Depends(get_db),
    sync: bool = Query(False),
) -> WorkflowRun:
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        return approve_run(db, run, actor=principal.name, sync=sync)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
