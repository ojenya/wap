"""Egress policy evaluation (domain allowlist)."""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EgressPolicy


def get_default_policy(db: Session) -> EgressPolicy:
    policy = db.scalar(select(EgressPolicy).where(EgressPolicy.name == "default"))
    if policy:
        return policy
    policy = EgressPolicy(
        name="default",
        allow_all=True,
        allowed_domains=[
            "github.com",
            "api.github.com",
            "gitlab.com",
            "registry.npmjs.org",
            "pypi.org",
            "files.pythonhosted.org",
            "opencode.ai",
            "cdn.playwright.dev",
        ],
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def domain_allowed(db: Session, url_or_host: str, environment_id: str | None = None) -> bool:
    host = url_or_host
    if "://" in url_or_host:
        host = urlparse(url_or_host).hostname or ""
    host = host.lower().removeprefix("www.")
    if environment_id:
        env_policy = db.scalar(
            select(EgressPolicy).where(EgressPolicy.environment_id == environment_id)
        )
        if env_policy:
            return _check(env_policy, host)
    policy = get_default_policy(db)
    return _check(policy, host)


def _check(policy: EgressPolicy, host: str) -> bool:
    if policy.allow_all:
        return True
    allowed = [d.lower().removeprefix("www.") for d in (policy.allowed_domains or [])]
    if host in allowed:
        return True
    return any(host.endswith(f".{d}") for d in allowed)
