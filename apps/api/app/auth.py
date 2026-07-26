"""API key auth, RBAC helpers, and simple in-memory rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ApiUser, UserRole
from app.security import hash_api_key

# Sliding-window counters keyed by api key hash / IP.
_RATE_WINDOWS: dict[str, deque[float]] = defaultdict(deque)


@dataclass
class Principal:
    name: str
    role: UserRole
    api_key_hash: str
    rate_limit_per_minute: int


def _open_dev_principal() -> Principal:
    return Principal(
        name="dev-admin",
        role=UserRole.admin,
        api_key_hash="open-dev",
        rate_limit_per_minute=get_settings().default_rate_limit_per_minute,
    )


def bootstrap_admin(db: Session) -> None:
    """Ensure the bootstrap admin API key exists when auth is required."""
    settings = get_settings()
    if not settings.auth_required or not settings.bootstrap_admin_key:
        return
    key_hash = hash_api_key(settings.bootstrap_admin_key)
    existing = db.scalar(select(ApiUser).where(ApiUser.api_key_hash == key_hash))
    if existing:
        return
    db.add(
        ApiUser(
            name="bootstrap-admin",
            api_key_hash=key_hash,
            role=UserRole.admin,
            rate_limit_per_minute=settings.default_rate_limit_per_minute,
        )
    )
    db.commit()


def _check_rate_limit(key: str, limit: int) -> None:
    now = time.time()
    window = _RATE_WINDOWS[key]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    window.append(now)


def get_principal(
    request: Request,
    db: Session = Depends(get_db),
    x_api_key: Annotated[str | None, Header()] = None,
) -> Principal:
    settings = get_settings()
    if not settings.auth_required:
        principal = _open_dev_principal()
        host = request.client.host if request.client else "local"
        _check_rate_limit(host, principal.rate_limit_per_minute)
        return principal

    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    key_hash = hash_api_key(x_api_key)
    user = db.scalar(select(ApiUser).where(ApiUser.api_key_hash == key_hash))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    principal = Principal(
        name=user.name,
        role=user.role,
        api_key_hash=user.api_key_hash,
        rate_limit_per_minute=user.rate_limit_per_minute,
    )
    _check_rate_limit(key_hash, principal.rate_limit_per_minute)
    return principal


def require_roles(*roles: UserRole):
    allowed = set(roles) | {UserRole.admin}

    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return principal

    return _dep


Operator = Annotated[
    Principal, Depends(require_roles(UserRole.admin, UserRole.operator))
]
Viewer = Annotated[
    Principal,
    Depends(require_roles(UserRole.admin, UserRole.operator, UserRole.viewer)),
]
Admin = Annotated[Principal, Depends(require_roles(UserRole.admin))]
