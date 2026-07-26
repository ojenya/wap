"""Human-in-the-loop: comments, steer notes, transcript events."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Operator, Viewer
from app.db import get_db
from app.events import emit_event
from app.models import RunComment, RunEvent, WorkflowRun

router = APIRouter(prefix="/api", tags=["hitl"])


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    kind: str = "comment"


class CommentOut(BaseModel):
    id: str
    run_id: str
    author: str
    body: str
    kind: str
    created_at: str


class EventOut(BaseModel):
    id: str
    run_id: str
    kind: str
    stage_name: str
    message: str
    payload: dict
    created_at: str


class SteerIn(BaseModel):
    guidance: str = Field(min_length=1, max_length=8000)


@router.get("/runs/{run_id}/events", response_model=list[EventOut])
def list_events(run_id: str, _: Viewer, db: Session = Depends(get_db)) -> list[EventOut]:
    if db.get(WorkflowRun, run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = db.scalars(
        select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.created_at.asc())
    )
    return [
        EventOut(
            id=e.id,
            run_id=e.run_id,
            kind=e.kind,
            stage_name=e.stage_name,
            message=e.message,
            payload=e.payload or {},
            created_at=e.created_at.isoformat(),
        )
        for e in rows
    ]


@router.get("/runs/{run_id}/comments", response_model=list[CommentOut])
def list_comments(run_id: str, _: Viewer, db: Session = Depends(get_db)) -> list[CommentOut]:
    if db.get(WorkflowRun, run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    rows = db.scalars(
        select(RunComment)
        .where(RunComment.run_id == run_id)
        .order_by(RunComment.created_at.asc())
    )
    return [
        CommentOut(
            id=c.id,
            run_id=c.run_id,
            author=c.author,
            body=c.body,
            kind=c.kind,
            created_at=c.created_at.isoformat(),
        )
        for c in rows
    ]


@router.post("/runs/{run_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    run_id: str,
    payload: CommentIn,
    principal: Operator,
    db: Session = Depends(get_db),
) -> CommentOut:
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    comment = RunComment(
        run_id=run_id,
        author=principal.name,
        body=payload.body,
        kind=payload.kind,
    )
    db.add(comment)
    emit_event(
        db,
        run_id=run_id,
        kind="hitl",
        message=f"comment by {principal.name}",
        payload={"body": payload.body[:500], "kind": payload.kind},
    )
    db.commit()
    db.refresh(comment)
    return CommentOut(
        id=comment.id,
        run_id=comment.run_id,
        author=comment.author,
        body=comment.body,
        kind=comment.kind,
        created_at=comment.created_at.isoformat(),
    )


@router.post("/runs/{run_id}/steer", response_model=CommentOut, status_code=201)
def steer_run(
    run_id: str,
    payload: SteerIn,
    principal: Operator,
    db: Session = Depends(get_db),
) -> CommentOut:
    """Attach steering guidance for the next develop retry / resume."""
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    comment = RunComment(
        run_id=run_id,
        author=principal.name,
        body=payload.guidance,
        kind="steer",
    )
    db.add(comment)
    emit_event(
        db,
        run_id=run_id,
        kind="hitl",
        stage_name="develop",
        message=f"steer by {principal.name}",
        payload={"guidance": payload.guidance[:800]},
    )
    db.commit()
    db.refresh(comment)
    return CommentOut(
        id=comment.id,
        run_id=comment.run_id,
        author=comment.author,
        body=comment.body,
        kind=comment.kind,
        created_at=comment.created_at.isoformat(),
    )

