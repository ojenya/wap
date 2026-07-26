"""Test fixtures: isolated in-memory SQLite DB and a FastAPI test client."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from app.db import Base

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    # Most unit tests run without a product worktree; relax the production
    # default playwright_required=True so sandbox_qa can skip there.
    # Strict E2E tests opt back in via require_playwright_e2e.
    from app.workflow_settings import get_or_create_config

    cfg = get_or_create_config(session)
    params = dict(cfg.params or {})
    params["playwright_required"] = False
    cfg.params = params
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def require_playwright_e2e(db_session):
    """Opt into strict product-worktree Playwright (skip = fail)."""
    from app.workflow_settings import get_or_create_config

    cfg = get_or_create_config(db_session)
    params = dict(cfg.params or {})
    params["playwright_required"] = True
    params["playwright_enabled"] = True
    cfg.params = params
    db_session.commit()
    return cfg


@pytest.fixture
def client(db_session):
    from app.db import get_db
    from app.main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
