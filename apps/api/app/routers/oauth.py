"""OAuth connect endpoints for GitLab / GitHub (PAT-free UX)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Operator, Viewer
from app.db import get_db
from app.models import OAuthConnection, OAuthProvider
from app.oauth_service import (
    OAuthServiceError,
    complete_oauth,
    connect_repository_from_oauth,
    delete_connection,
    list_connections,
    list_remote_repos,
    providers_status,
    start_oauth,
)
from app.routers.repos import _to_out
from app.schemas import RepositoryOut

router = APIRouter(prefix="/api/oauth", tags=["oauth"])


class CallbackIn(BaseModel):
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)


class ConnectRepoIn(BaseModel):
    external_id: str
    name: str
    clone_url: str
    default_branch: str = "main"
    path_filters: list[str] = Field(default_factory=list)


class ConnectionOut(BaseModel):
    id: str
    provider: str
    account_id: str
    account_login: str
    account_name: str
    scopes: str
    created_at: str
    updated_at: str


def _conn_out(c: OAuthConnection) -> ConnectionOut:
    return ConnectionOut(
        id=c.id,
        provider=c.provider.value,
        account_id=c.account_id,
        account_login=c.account_login,
        account_name=c.account_name,
        scopes=c.scopes,
        created_at=c.created_at.isoformat(),
        updated_at=c.updated_at.isoformat(),
    )


def _parse_provider(value: str) -> OAuthProvider:
    try:
        return OAuthProvider(value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Unknown OAuth provider") from exc


@router.get("/providers")
def get_providers(_: Viewer) -> dict:
    return providers_status()


@router.get("/connections", response_model=list[ConnectionOut])
def get_connections(_: Viewer, db: Session = Depends(get_db)) -> list[ConnectionOut]:
    return [_conn_out(c) for c in list_connections(db)]


@router.delete("/connections/{connection_id}", status_code=204)
def remove_connection(
    connection_id: str, _: Operator, db: Session = Depends(get_db)
) -> None:
    conn = db.get(OAuthConnection, connection_id)
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    delete_connection(db, conn)


@router.get("/{provider}/start")
def oauth_start(
    provider: str,
    _: Operator,
    db: Session = Depends(get_db),
    redirect_to: str = Query("/repositories"),
) -> dict:
    try:
        return start_oauth(db, _parse_provider(provider), redirect_to=redirect_to)
    except OAuthServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{provider}/callback", response_model=ConnectionOut)
def oauth_callback(
    provider: str,
    payload: CallbackIn,
    _: Operator,
    db: Session = Depends(get_db),
) -> ConnectionOut:
    try:
        conn = complete_oauth(
            db, _parse_provider(provider), code=payload.code, state=payload.state
        )
    except OAuthServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _conn_out(conn)


@router.get("/{provider}/callback")
def oauth_callback_redirect(
    provider: str,
    db: Session = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    """Optional server-side callback if redirect_uri points at the API."""
    frontend = "http://localhost:5173/repositories"
    if error:
        return RedirectResponse(
            f"{frontend}?oauth={provider}&error={error}",
            status_code=302,
        )
    if not code or not state:
        return RedirectResponse(
            f"{frontend}?oauth={provider}&error=missing_code",
            status_code=302,
        )
    try:
        complete_oauth(db, _parse_provider(provider), code=code, state=state)
    except OAuthServiceError as exc:
        return RedirectResponse(
            f"{frontend}?oauth={provider}&error={exc}",
            status_code=302,
        )
    return RedirectResponse(f"{frontend}?oauth={provider}&connected=1", status_code=302)


@router.get("/connections/{connection_id}/repos")
def connection_repos(
    connection_id: str,
    _: Viewer,
    db: Session = Depends(get_db),
    search: str = "",
) -> list[dict]:
    conn = db.get(OAuthConnection, connection_id)
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        return list_remote_repos(db, conn, search=search)
    except OAuthServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/connections/{connection_id}/repositories",
    response_model=RepositoryOut,
    status_code=201,
)
def connect_repo(
    connection_id: str,
    payload: ConnectRepoIn,
    _: Operator,
    db: Session = Depends(get_db),
) -> RepositoryOut:
    conn = db.get(OAuthConnection, connection_id)
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        repo = connect_repository_from_oauth(
            db,
            conn,
            external_id=payload.external_id,
            name=payload.name,
            clone_url=payload.clone_url,
            default_branch=payload.default_branch,
            path_filters=payload.path_filters,
        )
    except OAuthServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_out(repo)
