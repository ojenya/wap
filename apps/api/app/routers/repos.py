"""Connected git repository endpoints (GitLab / GitHub / generic git)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.git_workspace import GitWorkspaceError, GitWorkspaceManager, detect_provider
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
    )


def _sync(repo: Repository) -> None:
    mgr = GitWorkspaceManager()
    path = mgr.ensure_mirror(repo)
    repo.head_sha = mgr.resolve_head(path, repo.default_branch)
    repo.status = RepoStatus.ready
    repo.last_synced_at = datetime.now(UTC)
    repo.last_error = None


@router.get("", response_model=list[RepositoryOut])
def list_repositories(db: Session = Depends(get_db)) -> list[RepositoryOut]:
    rows = list(db.scalars(select(Repository).order_by(Repository.created_at.desc())))
    return [_to_out(r) for r in rows]


@router.post("", response_model=RepositoryOut, status_code=201)
def create_repository(payload: RepositoryCreate, db: Session = Depends(get_db)) -> RepositoryOut:
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
        status=RepoStatus.pending,
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)

    try:
        _sync(repo)
    except GitWorkspaceError as exc:
        repo.status = RepoStatus.error
        repo.last_error = str(exc)
    db.commit()
    db.refresh(repo)
    return _to_out(repo)


@router.get("/{repo_id}", response_model=RepositoryOut)
def get_repository(repo_id: str, db: Session = Depends(get_db)) -> RepositoryOut:
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return _to_out(repo)


@router.post("/{repo_id}/sync", response_model=RepositoryOut)
def sync_repository(repo_id: str, db: Session = Depends(get_db)) -> RepositoryOut:
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    try:
        _sync(repo)
    except GitWorkspaceError as exc:
        repo.status = RepoStatus.error
        repo.last_error = str(exc)
    db.commit()
    db.refresh(repo)
    return _to_out(repo)


@router.delete("/{repo_id}", status_code=204)
def delete_repository(repo_id: str, db: Session = Depends(get_db)) -> None:
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    db.delete(repo)
    db.commit()
