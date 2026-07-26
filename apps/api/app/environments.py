"""Environment definitions + snapshot refresh (local / Firecracker)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EnvBackend, Environment, EnvironmentStatus
from app.vm.backends import VmBackendError
from app.vm.manager import VmManager


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
    backend: str = "firecracker",
    vcpu_count: int = 2,
    mem_size_mib: int = 1024,
) -> Environment:
    try:
        backend_enum = EnvBackend(backend)
    except ValueError:
        backend_enum = EnvBackend.firecracker
    env = Environment(
        name=name,
        repository_id=repository_id,
        update_script=update_script,
        dockerfile_path=dockerfile_path,
        agents_md_path=agents_md_path,
        backend=backend_enum,
        vcpu_count=vcpu_count,
        mem_size_mib=mem_size_mib,
        status=EnvironmentStatus.draft,
    )
    db.add(env)
    db.commit()
    db.refresh(env)
    return env


def _validate_update_script(script: str) -> tuple[list[str], list[str] | None]:
    lines = [ln for ln in script.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    banned = ("docker compose up", "docker-compose up", "pnpm dev", "npm run dev", "uvicorn")
    bad = [ln for ln in lines if any(b in ln.lower() for b in banned)]
    return lines, bad or None


def refresh_environment(db: Session, env: Environment) -> Environment:
    """Run update-script policy checks, boot a short-lived VM, snapshot it."""
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

    lines, bad = _validate_update_script(script)
    log_lines = [f"$ {ln}" for ln in lines]
    if bad:
        env.status = EnvironmentStatus.error
        env.last_error = f"update_script contains banned start commands: {bad}"
        env.last_refresh_log = "\n".join([*log_lines, "ERROR: banned commands"])
        env.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(env)
        return env

    digest = hashlib.sha256(script.encode("utf-8")).hexdigest()[:16]
    env.snapshot_id = f"snap-{digest}"

    manager = VmManager(db)
    caps = manager.capabilities()
    log_lines.append(f"capabilities: {caps.reason}")
    log_lines.append(f"preferred_backend: {caps.preferred_backend}")

    try:
        # Materialize a tiny workspace marker so the VM has content to snapshot.
        from pathlib import Path

        from app.config import get_settings

        staging = Path(get_settings().data_dir).resolve() / "env-staging" / env.id
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "UPDATE_SCRIPT").write_text(script, encoding="utf-8")
        (staging / ".wap").mkdir(exist_ok=True)
        (staging / ".wap" / "env.json").write_text(
            f'{{"name": "{env.name}", "backend": "{env.backend.value}"}}\n',
            encoding="utf-8",
        )

        instance = manager.boot(env, workspace_src=staging)
        log_lines.append(f"booted instance={instance.id} backend={instance.backend.value}")
        # Execute update script lines inside the instance workspace (best-effort).
        for ln in lines:
            code, out = manager.exec(instance, env, ["bash", "-lc", ln], timeout=60)
            log_lines.append(f"exit={code} :: {ln}")
            if out.strip():
                log_lines.append(out.strip()[:500])
            if code != 0:
                # Soft-fail for missing tools in emulate/CI; still snapshot state.
                log_lines.append(f"WARN: command failed (continuing): {ln}")
        manager.snapshot(instance, env)
        log_lines.append(f"OK snapshot={env.snapshot_id} path={instance.snapshot_path}")
        manager.destroy(instance, env)
        log_lines.append("instance destroyed after snapshot")
        env.status = EnvironmentStatus.ready
        env.last_error = None
    except VmBackendError as exc:
        env.status = EnvironmentStatus.error
        env.last_error = str(exc)
        log_lines.append(f"ERROR: {exc}")

    env.last_refresh_log = "\n".join(log_lines)[:8000]
    env.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(env)
    return env


def environment_for_repository(db: Session, repository_id: str | None) -> Environment | None:
    if not repository_id:
        return None
    return db.scalar(
        select(Environment)
        .where(Environment.repository_id == repository_id)
        .order_by(Environment.updated_at.desc())
    )
