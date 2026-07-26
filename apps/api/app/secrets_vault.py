"""Scoped encrypted secrets vault (Cursor-like env/runtime/build)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SecretAccessLog, SecretScope, VaultSecret
from app.security import decrypt_secret, encrypt_secret


def put_secret(
    db: Session,
    *,
    name: str,
    value: str,
    scope: SecretScope = SecretScope.runtime,
    environment_id: str | None = None,
    description: str = "",
) -> VaultSecret:
    existing = db.scalar(
        select(VaultSecret).where(
            VaultSecret.name == name,
            VaultSecret.environment_id == environment_id,
            VaultSecret.scope == scope,
        )
    )
    cipher = encrypt_secret(value)
    if existing:
        existing.value_encrypted = cipher
        existing.description = description
        db.commit()
        db.refresh(existing)
        return existing
    secret = VaultSecret(
        name=name,
        scope=scope,
        environment_id=environment_id,
        value_encrypted=cipher,
        description=description,
    )
    db.add(secret)
    db.commit()
    db.refresh(secret)
    return secret


def reveal_secret(
    db: Session,
    *,
    secret_id: str,
    purpose: str,
    actor: str = "system",
) -> str | None:
    secret = db.get(VaultSecret, secret_id)
    if secret is None or not secret.value_encrypted:
        return None
    db.add(
        SecretAccessLog(
            repository_id=None,
            purpose=f"vault:{purpose}:{secret.name}",
            actor=actor,
        )
    )
    db.commit()
    return decrypt_secret(secret.value_encrypted)


def list_secret_metadata(db: Session, environment_id: str | None = None) -> list[VaultSecret]:
    q = select(VaultSecret).order_by(VaultSecret.created_at.desc())
    if environment_id:
        q = q.where(VaultSecret.environment_id == environment_id)
    return list(db.scalars(q))
