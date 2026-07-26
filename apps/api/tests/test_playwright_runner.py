"""Tests for product-worktree Playwright E2E sandbox."""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.playwright_runner import (
    _detect_start,
    _write_worktree_e2e_suite,
    run_playwright,
)


def test_no_worktree_skips_e2e(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        result = run_playwright(["loads home"], worktree_path=None, run_id="r1")
    finally:
        get_settings.cache_clear()
    assert result.mode == "skipped"
    assert result.all_passed is True
    assert all(r.status == "skipped" for r in result.results)


def test_detect_start_static_html(tmp_path: Path):
    (tmp_path / "index.html").write_text("<html><body>hi</body></html>", encoding="utf-8")
    cmd = _detect_start(tmp_path, 4173)
    assert cmd is not None
    assert "http.server" in cmd


def test_writes_e2e_suite_into_worktree(tmp_path: Path):
    suite = _write_worktree_e2e_suite(tmp_path, ["User can see the navbar"])
    assert (suite / "acceptance.spec.ts").exists()
    assert (suite / "playwright.config.ts").exists()
    text = (suite / "acceptance.spec.ts").read_text(encoding="utf-8")
    assert "User can see the navbar" in text


def test_required_e2e_fails_run_without_worktree(db_session, require_playwright_e2e):
    from app.models import RunStatus, StageStatus, Task
    from app.workflow.engine import run_workflow

    task = Task(title="Add logout button to navbar", require_approval=False)
    db_session.add(task)
    db_session.commit()

    run = run_workflow(db_session, task)
    assert run.status == RunStatus.failed
    sandbox = next(s for s in run.stages if s.name == "sandbox_qa")
    assert sandbox.status == StageStatus.failed
    assert "did not run" in (sandbox.error or "")


def test_worktree_static_e2e_passes_when_playwright_available(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    product = tmp_path / "product"
    product.mkdir()
    (product / "index.html").write_text(
        "<!doctype html><html><body><h1>Demo App</h1>"
        "<p data-testid='status'>ready</p></body></html>",
        encoding="utf-8",
    )

    try:
        result = run_playwright(
            ["Demo App loads and renders a body"],
            worktree_path=str(product),
            run_id="run-e2e-1",
            task_title="Demo App",
            timeout=90,
        )
    finally:
        get_settings.cache_clear()

    # Without Chromium browsers installed in the environment, runner skips
    # gracefully; with browsers, it must pass worktree-e2e.
    assert result.mode in {"worktree-e2e", "skipped"}
    if result.mode == "worktree-e2e":
        assert result.all_passed is True
        assert result.base_url
        assert result.artifact_dir
        arts = [a for r in result.results for a in r.artifacts]
        assert any(str(a).endswith(".png") for a in arts)
        assert (product / ".wap" / "e2e" / "acceptance.spec.ts").exists()
    else:
        assert result.all_passed is True
