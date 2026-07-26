"""Tests for connected repositories + per-run git worktrees."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.models import RepoProvider, Repository, RepoStatus, RunStatus, Task
from app.security import encrypt_secret
from app.workflow.engine import run_workflow


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    (path / "src").mkdir()
    (path / "src" / "auth.ts").write_text("export const auth = true;\n", encoding="utf-8")
    (path / "README.md").write_text("# demo\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True
    )


def test_workflow_uses_real_worktree(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    # Reset cached settings so APP_DATA_DIR is picked up.
    from app.config import get_settings

    get_settings.cache_clear()

    origin = tmp_path / "origin"
    _init_repo(origin)

    repo = Repository(
        name="demo",
        url=str(origin),
        provider=RepoProvider.git,
        default_branch="main",
        token_encrypted="",
        status=RepoStatus.pending,
    )
    db_session.add(repo)
    db_session.commit()

    task = Task(
        title="Improve auth module",
        description="small change",
        repository_id=repo.id,
        repo_url=str(origin),
        base_branch="main",
        task_type="feature",
        require_approval=False,
    )
    db_session.add(task)
    db_session.commit()

    run = run_workflow(db_session, task)

    assert run.status == RunStatus.completed
    assert run.worktree_path
    assert Path(run.worktree_path).exists()

    ctx = next(s for s in run.stages if s.name == "repository_context")
    assert ctx.output_payload["retrieval_strategy"].startswith("worktree")
    assert "src/auth.ts" in ctx.output_payload["retrieved_files"]

    develop = next(s for s in run.stages if s.name == "develop")
    assert develop.output_payload["develop_mode"] == "worktree-stub"
    assert develop.output_payload["diff"]
    assert (Path(run.worktree_path) / "src" / "auth.ts").exists()

    get_settings.cache_clear()


def test_audit_skips_develop_mutations(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    from app.config import get_settings

    get_settings.cache_clear()

    origin = tmp_path / "origin"
    _init_repo(origin)
    repo = Repository(
        name="demo", url=str(origin), provider=RepoProvider.git, default_branch="main"
    )
    db_session.add(repo)
    db_session.commit()
    task = Task(
        title="Security audit of auth",
        description="password and token review",
        repository_id=repo.id,
        base_branch="main",
        task_type="audit",
        require_approval=False,
    )
    db_session.add(task)
    db_session.commit()

    run = run_workflow(db_session, task)
    develop = next(s for s in run.stages if s.name == "develop")
    assert develop.output_payload.get("skipped") is True
    assert develop.output_payload.get("diff") == ""
    get_settings.cache_clear()


def test_create_repository_api(client, tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    from app.config import get_settings

    get_settings.cache_clear()

    origin = tmp_path / "origin"
    _init_repo(origin)

    resp = client.post(
        "/api/repositories",
        json={"name": "Local demo", "url": str(origin), "default_branch": "main"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ready"
    assert body["has_token"] is False
    assert body["head_sha"]

    listed = client.get("/api/repositories")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    get_settings.cache_clear()


def test_token_roundtrip_encrypted():
    cipher = encrypt_secret("glpat-secret-token")
    assert cipher != "glpat-secret-token"
    from app.security import decrypt_secret

    assert decrypt_secret(cipher) == "glpat-secret-token"
