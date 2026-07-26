"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import bootstrap_admin
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.egress import get_default_policy
from app.rag import _ensure_fts
from app.routers import (
    artifacts,
    automations,
    environments,
    hitl,
    learning,
    mcp,
    metrics,
    repos,
    secrets,
    tasks,
    workflow_config,
)
from app.workflow_settings import get_or_create_config

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        bootstrap_admin(db)
        get_or_create_config(db)
        get_default_policy(db)
        _ensure_fts(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)
app.include_router(repos.router)
app.include_router(metrics.router)
app.include_router(workflow_config.router)
app.include_router(learning.router)
app.include_router(environments.router)
app.include_router(secrets.router)
app.include_router(artifacts.router)
app.include_router(hitl.router)
app.include_router(automations.router)
app.include_router(mcp.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
