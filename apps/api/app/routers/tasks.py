"""Task and workflow-run endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Repository, Task, WorkflowRun
from app.schemas import TaskCreate, TaskDetailOut, TaskOut, WorkflowRunOut
from app.workflow.engine import run_workflow
from app.workflow.registry import WORKFLOWS

router = APIRouter(prefix="/api", tags=["tasks"])


@router.get("/workflows")
def list_workflows() -> dict[str, list[str]]:
    """Expose the versioned workflow definitions as a read-only graph."""
    return {
        version: [stage_cls.name for stage_cls in stages]
        for version, stages in WORKFLOWS.items()
    }


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> Task:
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
def list_tasks(db: Session = Depends(get_db)) -> list[Task]:
    return list(db.scalars(select(Task).order_by(Task.created_at.desc())))


@router.get("/tasks/{task_id}", response_model=TaskDetailOut)
def get_task(task_id: str, db: Session = Depends(get_db)) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks/{task_id}/runs", response_model=WorkflowRunOut, status_code=201)
def start_run(task_id: str, db: Session = Depends(get_db)) -> WorkflowRun:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return run_workflow(db, task)


@router.get("/runs/{run_id}", response_model=WorkflowRunOut)
def get_run(run_id: str, db: Session = Depends(get_db)) -> WorkflowRun:
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
