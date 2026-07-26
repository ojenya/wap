"""Environment definitions + snapshot refresh (Cursor Cloud–inspired)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Environment, EnvironmentStatus


def list_environments(db: Session) -> list[Environment]:
    return list(db.scalars(select(Environment).order_by(Environment.created_at.desc())))


def create_environment(
    db: Session,
    *,
    name: str,
    repository_id: str | None = None,
    update_script: str = "pnpm install\npip install -e .",
    dockerfile_path: str = ".cursor/Dockerfile",
    agents_md_path: str = "AGENTS.md",
) -> Environment:
    env = Environment(
        name=name,
        repository_id=repository_id,
        update_script=update_script,
        dockerfile_path=dockerfile_path,
        agents_md_path=agents_md_path,
        status=EnvironmentStatus.draft,
    )
    db.add(env)
    db.commit()
    db.refresh(env)
    return env


def refresh_environment(db: Session, env: Environment) -> Environment:
    """Idempotent 'update script' simulation + snapshot id minting.

    Real VM snapshotting is an extension seam; here we validate the script is
    non-empty, record a refresh log, and stamp a deterministic snapshot id.
    """
    env.status = EnvironmentStatus.refreshing
    db.commit()
    script = (env.update_script or "").strip()
    if not script:
        env.status = EnvironmentStatus.error
        env.last_error = "update_script is empty"
        env.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(env)
        return env

    lines = [ln for ln in script.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    # Reject brittle service-start commands (Cursor Cloud update-script policy).
    banned = ("docker compose up", "docker-compose up", "pnpm dev", "npm run dev", "uvicorn")
    bad = [ln for ln in lines if any(b in ln.lower() for b in banned)]
    log_lines = [f"$ {ln}" for ln in lines]
    if bad:
        env.status = EnvironmentStatus.error
        env.last_error = f"update_script contains banned start commands: {bad}"
        env.last_refresh_log = "\n".join(log_lines + ["ERROR: banned commands"])
        env.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(env)
        return env

    digest = hashlib.sha256(script.encode("utf-8")).hexdigest()[:16]
    env.snapshot_id = f"snap-{digest}"
    env.status = EnvironmentStatus.ready
    env.last_error = None
    env.last_refresh_log = "\n".join(
        [*log_lines, f"OK snapshot={env.snapshot_id}", "refresh complete"]
    )
    env.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(env)
    return env
