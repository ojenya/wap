"""SCM OAuth connections: GitLab + GitHub (no PAT required in the UI)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import github_client, gitlab_client
from app.config import get_settings
from app.git_workspace import GitWorkspaceError, GitWorkspaceManager, detect_provider
from app.models import (
    OAuthConnection,
    OAuthProvider,
    OAuthState,
    RepoProvider,
    Repository,
    RepoStatus,
)
from app.security import decrypt_secret, encrypt_secret


class OAuthServiceError(RuntimeError):
    pass


def providers_status() -> dict[str, dict[str, Any]]:
    settings = get_settings()
    return {
        "gitlab": {
            "configured": gitlab_client.oauth_configured(),
            "authorize_available": bool(settings.gitlab_oauth_client_id),
            "redirect_uri": settings.gitlab_oauth_redirect_uri,
            "base_url": settings.gitlab_base_url,
        },
        "github": {
            "configured": github_client.oauth_configured(),
            "authorize_available": bool(settings.github_oauth_client_id),
            "redirect_uri": settings.github_oauth_redirect_uri,
            "base_url": "https://github.com",
        },
    }


def start_oauth(db: Session, provider: OAuthProvider, redirect_to: str = "/repositories") -> dict:
    state = secrets.token_urlsafe(24)
    db.add(
        OAuthState(
            provider=provider,
            state=state,
            redirect_to=redirect_to or "/repositories",
        )
    )
    db.commit()
    if provider == OAuthProvider.gitlab:
        url = gitlab_client.oauth_authorize_url(state=state)
        if not url:
            raise OAuthServiceError("GitLab OAuth client id is not configured")
        return {"url": url, "state": state, "provider": provider.value}
    if provider == OAuthProvider.github:
        url = github_client.oauth_authorize_url(state=state)
        if not url:
            raise OAuthServiceError("GitHub OAuth client id is not configured")
        return {"url": url, "state": state, "provider": provider.value}
    raise OAuthServiceError(f"Unsupported provider: {provider}")


def _consume_state(db: Session, provider: OAuthProvider, state: str) -> OAuthState:
    row = db.scalar(
        select(OAuthState).where(
            OAuthState.state == state,
            OAuthState.provider == provider,
            OAuthState.consumed.is_(False),
        )
    )
    if row is None:
        raise OAuthServiceError("Invalid or expired OAuth state")
    # 15-minute TTL
    created = row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    age = datetime.now(UTC) - created
    if age > timedelta(minutes=15):
        row.consumed = True
        db.commit()
        raise OAuthServiceError("OAuth state expired — start again")
    row.consumed = True
    db.commit()
    return row


def complete_oauth(
    db: Session, provider: OAuthProvider, *, code: str, state: str
) -> OAuthConnection:
    _consume_state(db, provider, state)
    if provider == OAuthProvider.gitlab:
        token_payload = gitlab_client.oauth_exchange_code(code)
        access = token_payload["access_token"]
        user = gitlab_client.fetch_current_user(access)
        account_id = str(user.get("id", ""))
        login = str(user.get("username") or user.get("name") or account_id)
        name = str(user.get("name") or login)
        scopes = str(token_payload.get("scope") or "api")
        refresh = str(token_payload.get("refresh_token") or "")
        expires_in = token_payload.get("expires_in")
    elif provider == OAuthProvider.github:
        token_payload = github_client.oauth_exchange_code(code)
        access = token_payload["access_token"]
        user = github_client.fetch_current_user(access)
        account_id = str(user.get("id", ""))
        login = str(user.get("login") or account_id)
        name = str(user.get("name") or login)
        scopes = str(token_payload.get("scope") or github_client.DEFAULT_SCOPES)
        refresh = ""
        expires_in = None
    else:
        raise OAuthServiceError(f"Unsupported provider: {provider}")

    expires_at = None
    if expires_in:
        try:
            expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))
        except (TypeError, ValueError):
            expires_at = None

    existing = db.scalar(
        select(OAuthConnection).where(
            OAuthConnection.provider == provider,
            OAuthConnection.account_id == account_id,
        )
    )
    if existing:
        existing.access_token_encrypted = encrypt_secret(access)
        existing.refresh_token_encrypted = encrypt_secret(refresh) if refresh else ""
        existing.scopes = scopes
        existing.account_login = login
        existing.account_name = name
        existing.expires_at = expires_at
        existing.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(existing)
        return existing

    conn = OAuthConnection(
        provider=provider,
        account_id=account_id,
        account_login=login,
        account_name=name,
        access_token_encrypted=encrypt_secret(access),
        refresh_token_encrypted=encrypt_secret(refresh) if refresh else "",
        scopes=scopes,
        expires_at=expires_at,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


def list_connections(db: Session) -> list[OAuthConnection]:
    return list(db.scalars(select(OAuthConnection).order_by(OAuthConnection.created_at.desc())))


def get_access_token(db: Session, conn: OAuthConnection) -> str:
    if not conn.access_token_encrypted:
        raise OAuthServiceError("Connection has no access token")
    return decrypt_secret(conn.access_token_encrypted)


def list_remote_repos(
    db: Session, conn: OAuthConnection, search: str = ""
) -> list[dict[str, Any]]:
    token = get_access_token(db, conn)
    if conn.provider == OAuthProvider.gitlab:
        projects = gitlab_client.list_projects(token, search=search)
        return [
            {
                "external_id": str(p.id),
                "name": p.name,
                "full_name": p.path_with_namespace,
                "clone_url": p.http_url_to_repo,
                "default_branch": p.default_branch,
                "provider": "gitlab",
            }
            for p in projects
        ]
    if conn.provider == OAuthProvider.github:
        repos = github_client.list_user_repos(token, search=search)
        return [
            {
                "external_id": str(r["id"]),
                "name": r["name"],
                "full_name": r["full_name"],
                "clone_url": r["clone_url"],
                "default_branch": r.get("default_branch") or "main",
                "provider": "github",
            }
            for r in repos
        ]
    raise OAuthServiceError(f"Unsupported provider: {conn.provider}")


def connect_repository_from_oauth(
    db: Session,
    conn: OAuthConnection,
    *,
    external_id: str,
    name: str,
    clone_url: str,
    default_branch: str = "main",
    path_filters: list[str] | None = None,
) -> Repository:
    token = get_access_token(db, conn)
    provider = detect_provider(clone_url)
    try:
        provider_enum = RepoProvider(provider)
    except ValueError:
        provider_enum = (
            RepoProvider.gitlab
            if conn.provider == OAuthProvider.gitlab
            else RepoProvider.github
        )

    gitlab_project_id = None
    if conn.provider == OAuthProvider.gitlab and external_id.isdigit():
        gitlab_project_id = int(external_id)

    repo = Repository(
        name=name.strip() or clone_url,
        url=clone_url.strip(),
        provider=provider_enum,
        default_branch=default_branch or "main",
        token_encrypted=encrypt_secret(token),
        gitlab_project_id=gitlab_project_id,
        path_filters=path_filters or [],
        status=RepoStatus.pending,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    try:
        mgr = GitWorkspaceManager()
        path = mgr.ensure_mirror(repo, db=db)
        repo.head_sha = mgr.resolve_head(path, repo.default_branch)
        repo.status = RepoStatus.ready
        repo.last_synced_at = datetime.now(UTC)
        repo.last_error = None
    except GitWorkspaceError as exc:
        repo.status = RepoStatus.error
        repo.last_error = str(exc)
    db.commit()
    db.refresh(repo)
    return repo


def delete_connection(db: Session, conn: OAuthConnection) -> None:
    db.delete(conn)
    db.commit()
