"""Environment CRUD + snapshot refresh."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Operator, Viewer
from app.db import get_db
from app.environments import create_environment, list_environments, refresh_environment
from app.models import Environment

router = APIRouter(prefix="/api/environments", tags=["environments"])


class EnvironmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    repository_id: str | None = None
    update_script: str = "pnpm install\npip install -e ."
    dockerfile_path: str = ".cursor/Dockerfile"
    agents_md_path: str = "AGENTS.md"


class EnvironmentOut(BaseModel):
    id: str
    name: str
    repository_id: str | None
    dockerfile_path: str
    environment_json_path: str
    update_script: str
    agents_md_path: str
    snapshot_id: str | None
    status: str
    last_refresh_log: str
    last_error: str | None
    created_at: str
    updated_at: str


def _out(env: Environment) -> EnvironmentOut:
    return EnvironmentOut(
        id=env.id,
        name=env.name,
        repository_id=env.repository_id,
        dockerfile_path=env.dockerfile_path,
        environment_json_path=env.environment_json_path,
        update_script=env.update_script,
        agents_md_path=env.agents_md_path,
        snapshot_id=env.snapshot_id,
        status=env.status.value,
        last_refresh_log=env.last_refresh_log,
        last_error=env.last_error,
        created_at=env.created_at.isoformat(),
        updated_at=env.updated_at.isoformat(),
    )


@router.get("", response_model=list[EnvironmentOut])
def list_envs(_: Viewer, db: Session = Depends(get_db)) -> list[EnvironmentOut]:
    return [_out(e) for e in list_environments(db)]


@router.post("", response_model=EnvironmentOut, status_code=201)
def create_env(
    payload: EnvironmentIn, _: Operator, db: Session = Depends(get_db)
) -> EnvironmentOut:
    env = create_environment(
        db,
        name=payload.name,
        repository_id=payload.repository_id,
        update_script=payload.update_script,
        dockerfile_path=payload.dockerfile_path,
        agents_md_path=payload.agents_md_path,
    )
    return _out(env)


@router.post("/{env_id}/refresh", response_model=EnvironmentOut)
def refresh_env(env_id: str, _: Operator, db: Session = Depends(get_db)) -> EnvironmentOut:
    env = db.get(Environment, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return _out(refresh_environment(db, env))


@router.get("/{env_id}", response_model=EnvironmentOut)
def get_env(env_id: str, _: Viewer, db: Session = Depends(get_db)) -> EnvironmentOut:
    env = db.get(Environment, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return _out(env)
