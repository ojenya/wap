"""Connected git repository endpoints + GitLab project browser."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Operator, Viewer
from app.db import get_db
from app.git_workspace import GitWorkspaceError, GitWorkspaceManager, detect_provider
from app.gitlab_client import (
    GitLabError,
    list_branches,
    list_projects,
    oauth_authorize_url,
    oauth_exchange_code,
)
from app.models import RepoProvider, Repository, RepoStatus
from app.schemas import RepositoryCreate, RepositoryOut
from app.security import encrypt_secret

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


def _to_out(repo: Repository) -> RepositoryOut:
    return RepositoryOut(
        id=repo.id,
        name=repo.name,
        url=repo.url,
        provider=repo.provider.value if hasattr(repo.provider, "value") else str(repo.provider),
        default_branch=repo.default_branch,
        status=repo.status.value if hasattr(repo.status, "value") else str(repo.status),
        last_error=repo.last_error,
        last_synced_at=repo.last_synced_at,
        head_sha=repo.head_sha,
        created_at=repo.created_at,
        has_token=bool(repo.token_encrypted),
        gitlab_project_id=repo.gitlab_project_id,
        path_filters=repo.path_filters or [],
    )


def _sync(repo: Repository, db: Session) -> None:
    mgr = GitWorkspaceManager()
    path = mgr.ensure_mirror(repo, db=db)
    repo.head_sha = mgr.resolve_head(path, repo.default_branch)
    repo.status = RepoStatus.ready
    repo.last_synced_at = datetime.now(UTC)
    repo.last_error = None


@router.get("", response_model=list[RepositoryOut])
def list_repositories(_: Viewer, db: Session = Depends(get_db)) -> list[RepositoryOut]:
    rows = list(db.scalars(select(Repository).order_by(Repository.created_at.desc())))
    return [_to_out(r) for r in rows]


@router.post("", response_model=RepositoryOut, status_code=201)
def create_repository(
    payload: RepositoryCreate, _: Operator, db: Session = Depends(get_db)
) -> RepositoryOut:
    provider = payload.provider or detect_provider(payload.url)
    try:
        provider_enum = RepoProvider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Unknown provider: {provider}") from exc

    repo = Repository(
        name=payload.name.strip(),
        url=payload.url.strip(),
        provider=provider_enum,
        default_branch=payload.default_branch or "main",
        token_encrypted=encrypt_secret(payload.token) if payload.token else "",
        gitlab_project_id=payload.gitlab_project_id,
        path_filters=payload.path_filters or [],
        status=RepoStatus.pending,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    try:
        _sync(repo, db)
    except GitWorkspaceError as exc:
        repo.status = RepoStatus.error
        repo.last_error = str(exc)
    db.commit()
    db.refresh(repo)
    return _to_out(repo)


# --- GitLab browser (static paths BEFORE /{repo_id}) ---


@router.get("/gitlab/oauth-url")
def gitlab_oauth_url(_: Operator) -> dict[str, str | None]:
    return {"url": oauth_authorize_url()}


@router.post("/gitlab/oauth/callback")
def gitlab_oauth_callback(payload: dict, _: Operator) -> dict[str, str]:
    """Legacy callback — prefer /api/oauth/gitlab/callback (stores connection)."""
    code = payload.get("code")
    if not code:
        raise HTTPException(status_code=422, detail="code is required")
    try:
        token_payload = oauth_exchange_code(code)
    except GitLabError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"access_token": str(token_payload["access_token"])}


@router.get("/gitlab/projects")
def gitlab_projects(
    _: Operator,
    token: str = Query(..., min_length=3),
    search: str = "",
) -> list[dict]:
    try:
        projects = list_projects(token, search=search)
    except GitLabError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        {
            "id": p.id,
            "name": p.name,
            "path_with_namespace": p.path_with_namespace,
            "http_url_to_repo": p.http_url_to_repo,
            "default_branch": p.default_branch,
        }
        for p in projects
    ]


@router.get("/gitlab/projects/{project_id}/branches")
def gitlab_branches(
    project_id: int, _: Operator, token: str = Query(..., min_length=3)
) -> list[str]:
    try:
        return list_branches(token, project_id)
    except GitLabError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{repo_id}", response_model=RepositoryOut)
def get_repository(repo_id: str, _: Viewer, db: Session = Depends(get_db)) -> RepositoryOut:
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return _to_out(repo)


@router.post("/{repo_id}/sync", response_model=RepositoryOut)
def sync_repository(repo_id: str, _: Operator, db: Session = Depends(get_db)) -> RepositoryOut:
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    try:
        _sync(repo, db)
    except GitWorkspaceError as exc:
        repo.status = RepoStatus.error
        repo.last_error = str(exc)
    db.commit()
    db.refresh(repo)
    return _to_out(repo)


@router.delete("/{repo_id}", status_code=204)
def delete_repository(repo_id: str, _: Operator, db: Session = Depends(get_db)) -> None:
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    db.delete(repo)
    db.commit()
