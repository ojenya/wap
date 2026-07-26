"""Secrets vault + egress policy API (no plaintext responses)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Operator, Viewer
from app.db import get_db
from app.egress import domain_allowed, get_default_policy
from app.models import SecretScope
from app.secrets_vault import list_secret_metadata, put_secret

router = APIRouter(prefix="/api", tags=["secrets"])


class SecretIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1)
    scope: str = "runtime"
    environment_id: str | None = None
    description: str = ""


class SecretOut(BaseModel):
    id: str
    name: str
    scope: str
    environment_id: str | None
    description: str
    created_at: str
    has_value: bool = True


class EgressOut(BaseModel):
    id: str
    name: str
    allow_all: bool
    allowed_domains: list[str]
    environment_id: str | None


class EgressUpdate(BaseModel):
    allow_all: bool | None = None
    allowed_domains: list[str] | None = None


class EgressCheckIn(BaseModel):
    url: str


@router.get("/secrets", response_model=list[SecretOut])
def list_secrets(
    _: Operator,
    db: Session = Depends(get_db),
    environment_id: str | None = None,
) -> list[SecretOut]:
    return [
        SecretOut(
            id=s.id,
            name=s.name,
            scope=s.scope.value,
            environment_id=s.environment_id,
            description=s.description,
            created_at=s.created_at.isoformat(),
            has_value=bool(s.value_encrypted),
        )
        for s in list_secret_metadata(db, environment_id)
    ]


@router.post("/secrets", response_model=SecretOut, status_code=201)
def create_secret(payload: SecretIn, _: Operator, db: Session = Depends(get_db)) -> SecretOut:
    try:
        scope = SecretScope(payload.scope)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid scope") from exc
    secret = put_secret(
        db,
        name=payload.name,
        value=payload.value,
        scope=scope,
        environment_id=payload.environment_id,
        description=payload.description,
    )
    return SecretOut(
        id=secret.id,
        name=secret.name,
        scope=secret.scope.value,
        environment_id=secret.environment_id,
        description=secret.description,
        created_at=secret.created_at.isoformat(),
        has_value=True,
    )


@router.get("/egress-policy", response_model=EgressOut)
def get_egress(_: Viewer, db: Session = Depends(get_db)) -> EgressOut:
    p = get_default_policy(db)
    return EgressOut(
        id=p.id,
        name=p.name,
        allow_all=p.allow_all,
        allowed_domains=list(p.allowed_domains or []),
        environment_id=p.environment_id,
    )


@router.put("/egress-policy", response_model=EgressOut)
def update_egress(
    payload: EgressUpdate, _: Operator, db: Session = Depends(get_db)
) -> EgressOut:
    p = get_default_policy(db)
    if payload.allow_all is not None:
        p.allow_all = payload.allow_all
    if payload.allowed_domains is not None:
        p.allowed_domains = payload.allowed_domains
    db.commit()
    db.refresh(p)
    return EgressOut(
        id=p.id,
        name=p.name,
        allow_all=p.allow_all,
        allowed_domains=list(p.allowed_domains or []),
        environment_id=p.environment_id,
    )


@router.post("/egress-policy/check")
def check_egress(payload: EgressCheckIn, _: Viewer, db: Session = Depends(get_db)) -> dict:
    return {"url": payload.url, "allowed": domain_allowed(db, payload.url)}
