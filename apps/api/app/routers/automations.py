"""Automations CRUD + webhook/cron triggers."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Operator, Viewer
from app.automations import due_cron_automations, new_webhook_token, trigger_automation
from app.db import get_db
from app.models import Automation, AutomationTrigger

router = APIRouter(prefix="/api/automations", tags=["automations"])


class AutomationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    trigger_type: str = "webhook"
    cron_expr: str = ""
    repository_id: str | None = None
    task_title_template: str = "Automation: {{name}}"
    task_description_template: str = ""
    task_type: str = "bug_fix"
    auto_start: bool = True


class AutomationOut(BaseModel):
    id: str
    name: str
    enabled: bool
    trigger_type: str
    cron_expr: str
    webhook_token: str
    repository_id: str | None
    task_title_template: str
    task_description_template: str
    task_type: str
    auto_start: bool
    last_triggered_at: str | None
    created_at: str


def _out(a: Automation) -> AutomationOut:
    return AutomationOut(
        id=a.id,
        name=a.name,
        enabled=a.enabled,
        trigger_type=a.trigger_type.value,
        cron_expr=a.cron_expr,
        webhook_token=a.webhook_token,
        repository_id=a.repository_id,
        task_title_template=a.task_title_template,
        task_description_template=a.task_description_template,
        task_type=a.task_type,
        auto_start=a.auto_start,
        last_triggered_at=a.last_triggered_at.isoformat() if a.last_triggered_at else None,
        created_at=a.created_at.isoformat(),
    )


@router.get("", response_model=list[AutomationOut])
def list_automations(_: Viewer, db: Session = Depends(get_db)) -> list[AutomationOut]:
    rows = db.scalars(select(Automation).order_by(Automation.created_at.desc()))
    return [_out(a) for a in rows]


@router.post("", response_model=AutomationOut, status_code=201)
def create_automation(
    payload: AutomationIn, _: Operator, db: Session = Depends(get_db)
) -> AutomationOut:
    try:
        trigger = AutomationTrigger(payload.trigger_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid trigger_type") from exc
    a = Automation(
        name=payload.name,
        enabled=payload.enabled,
        trigger_type=trigger,
        cron_expr=payload.cron_expr,
        webhook_token=new_webhook_token(),
        repository_id=payload.repository_id,
        task_title_template=payload.task_title_template,
        task_description_template=payload.task_description_template,
        task_type=payload.task_type,
        auto_start=payload.auto_start,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _out(a)


@router.post("/{automation_id}/trigger")
def manual_trigger(
    automation_id: str,
    _: Operator,
    db: Session = Depends(get_db),
    sync: bool = False,
) -> dict:
    a = db.get(Automation, automation_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    try:
        return trigger_automation(db, a, payload={"source": "manual"}, sync_run=sync)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/webhook/{token}")
def webhook_trigger(token: str, payload: dict | None = None, db: Session = Depends(get_db)) -> dict:
    a = db.scalar(select(Automation).where(Automation.webhook_token == token))
    if a is None:
        raise HTTPException(status_code=404, detail="Unknown webhook token")
    try:
        return trigger_automation(db, a, payload=payload or {}, sync_run=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/cron/tick")
def cron_tick(_: Operator, db: Session = Depends(get_db), sync: bool = False) -> dict:
    rows = list(db.scalars(select(Automation)))
    due = due_cron_automations(rows)
    results = []
    for a in due:
        results.append(trigger_automation(db, a, payload={"source": "cron"}, sync_run=sync))
    return {"triggered": len(results), "results": results}
