"""Automation triggers → create task (+ optional async run)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Automation, AutomationTrigger, Task
from app.workflow.engine import start_workflow_async


def new_webhook_token() -> str:
    return secrets.token_urlsafe(24)


def render_template(template: str, **ctx: Any) -> str:
    out = template
    for key, value in ctx.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out


def trigger_automation(
    db: Session,
    automation: Automation,
    *,
    payload: dict[str, Any] | None = None,
    sync_run: bool = False,
) -> dict[str, Any]:
    if not automation.enabled:
        raise ValueError("Automation is disabled")
    payload = payload or {}
    title = render_template(
        automation.task_title_template,
        name=automation.name,
        **{k: payload.get(k, "") for k in ("title", "ref", "author")},
    )
    description = render_template(
        automation.task_description_template or f"Triggered by {automation.trigger_type.value}",
        name=automation.name,
        payload=str(payload)[:2000],
    )
    task = Task(
        title=title[:200],
        description=description,
        repository_id=automation.repository_id,
        task_type=automation.task_type,
        require_approval=False,
    )
    db.add(task)
    automation.last_triggered_at = datetime.now(UTC)
    db.commit()
    db.refresh(task)

    run_id = None
    if automation.auto_start:
        if sync_run:
            from app.workflow.engine import run_workflow

            run = run_workflow(db, task)
            run_id = run.id
        else:
            run_id = start_workflow_async(task.id)

    return {
        "automation_id": automation.id,
        "task_id": task.id,
        "run_id": run_id,
        "trigger_type": automation.trigger_type.value,
    }


def due_cron_automations(
    automations: list[Automation], now: datetime | None = None
) -> list[Automation]:
    """Naive due check: hourly/daily presets when last trigger is stale or missing."""
    now = now or datetime.now(UTC)
    due: list[Automation] = []
    for a in automations:
        if not a.enabled or a.trigger_type != AutomationTrigger.cron:
            continue
        if a.cron_expr not in {"hourly", "daily", "* * * * *"}:
            # Only simple presets in MVP; others ignored until a real scheduler lands.
            continue
        if a.last_triggered_at is None:
            due.append(a)
            continue
        delta = now - a.last_triggered_at
        if a.cron_expr == "hourly" and delta.total_seconds() >= 3600:
            due.append(a)
        elif a.cron_expr in {"daily", "* * * * *"} and delta.total_seconds() >= 86400:
            due.append(a)
    return due
