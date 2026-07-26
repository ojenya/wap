"""Safe workflow parameter editor API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import Admin, Viewer
from app.db import get_db
from app.schemas import WorkflowConfigOut, WorkflowConfigUpdate
from app.workflow_settings import ALLOWED_KEYS, get_or_create_config, update_config

router = APIRouter(prefix="/api/workflow-config", tags=["workflow-config"])


@router.get("", response_model=WorkflowConfigOut)
def get_config(_: Viewer, db: Session = Depends(get_db)) -> WorkflowConfigOut:
    cfg = get_or_create_config(db)
    return WorkflowConfigOut(
        name=cfg.name,
        version=cfg.version,
        params=cfg.params or {},
        updated_at=cfg.updated_at,
        allowed_keys=sorted(ALLOWED_KEYS),
    )


@router.put("", response_model=WorkflowConfigOut)
def put_config(
    payload: WorkflowConfigUpdate, _: Admin, db: Session = Depends(get_db)
) -> WorkflowConfigOut:
    cfg = update_config(db, "default", payload.params)
    return WorkflowConfigOut(
        name=cfg.name,
        version=cfg.version,
        params=cfg.params or {},
        updated_at=cfg.updated_at,
        allowed_keys=sorted(ALLOWED_KEYS),
    )
