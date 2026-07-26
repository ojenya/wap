"""Append-only run transcript / observability helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import RunEvent


def emit_event(
    db: Session,
    *,
    run_id: str,
    kind: str,
    message: str,
    stage_name: str = "",
    payload: dict[str, Any] | None = None,
    commit: bool = False,
) -> RunEvent:
    event = RunEvent(
        run_id=run_id,
        kind=kind,
        stage_name=stage_name,
        message=message,
        payload=payload or {},
    )
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    return event
