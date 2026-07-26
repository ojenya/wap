"""Coverage for Cursor Cloud–inspired platform features."""

from __future__ import annotations

from sqlalchemy import select

from app.automations import due_cron_automations, trigger_automation
from app.computer_use import prepare_desktop_session
from app.egress import domain_allowed, get_default_policy
from app.environments import create_environment, refresh_environment
from app.events import emit_event
from app.github_client import parse_github_repo
from app.mcp_registry import invoke_tool, register_server
from app.models import (
    Automation,
    AutomationTrigger,
    EnvironmentStatus,
    McpTransport,
    RunEvent,
    RunStatus,
    SecretScope,
    Task,
    WorkflowRun,
)
from app.secrets_vault import list_secret_metadata, put_secret, reveal_secret
from app.workflow.engine import run_workflow
from app.workflow.parallel import run_parallel_subagents


def test_environment_refresh_mints_snapshot(db_session):
    env = create_environment(
        db_session,
        name="demo-env",
        update_script="pnpm install\npip install -e .",
    )
    refreshed = refresh_environment(db_session, env)
    assert refreshed.status == EnvironmentStatus.ready
    assert refreshed.snapshot_id and refreshed.snapshot_id.startswith("snap-")


def test_environment_rejects_banned_update_commands(db_session):
    env = create_environment(
        db_session, name="bad", update_script="pnpm install\npnpm dev"
    )
    refreshed = refresh_environment(db_session, env)
    assert refreshed.status == EnvironmentStatus.error
    assert "banned" in (refreshed.last_error or "")


def test_secrets_vault_encrypts_and_audits(db_session):
    secret = put_secret(
        db_session,
        name="OPENAI_API_KEY",
        value="sk-test-secret",
        scope=SecretScope.runtime,
    )
    meta = list_secret_metadata(db_session)
    assert meta[0].name == "OPENAI_API_KEY"
    assert "sk-test" not in meta[0].value_encrypted
    plain = reveal_secret(
        db_session, secret_id=secret.id, purpose="unit-test", actor="tester"
    )
    assert plain == "sk-test-secret"


def test_egress_policy_allowlist(db_session):
    policy = get_default_policy(db_session)
    policy.allow_all = False
    policy.allowed_domains = ["github.com", "pypi.org"]
    db_session.commit()
    assert domain_allowed(db_session, "https://github.com/ojenya/wap") is True
    assert domain_allowed(db_session, "https://evil.example") is False


def test_parallel_subagents_fan_out():
    result = run_parallel_subagents("Add logout", ["src/nav.ts", "tests/nav.test.ts"])
    assert result["parallel"] is True
    roles = {s["role"] for s in result["subagents"]}
    assert roles == {"explore", "fix", "test"}
    assert result["merged_findings"]


def test_desktop_session_ready_with_url():
    session = prepare_desktop_session(
        worktree_path="/tmp/wt",
        base_url="http://127.0.0.1:4173",
        scenarios=["loads home"],
    )
    assert session.status == "ready"
    assert session.takeover_supported is True


def test_parse_github_repo():
    assert parse_github_repo("https://github.com/ojenya/wap.git") == ("ojenya", "wap")
    assert parse_github_repo("git@github.com:ojenya/wap.git") == ("ojenya", "wap")


def test_mcp_ping(db_session):
    server = register_server(
        db_session,
        name="context7",
        transport=McpTransport.http,
        url="https://example.com/mcp",
    )
    out = invoke_tool(db_session, server, "context7.ping", {})
    assert out["ok"] is True


def test_automation_webhook_creates_task(db_session):
    auto = Automation(
        name="nightly",
        trigger_type=AutomationTrigger.webhook,
        webhook_token="tok-test",
        task_title_template="Auto: {{name}}",
        auto_start=False,
    )
    db_session.add(auto)
    db_session.commit()
    result = trigger_automation(
        db_session, auto, payload={"source": "hook"}, sync_run=False
    )
    task = db_session.get(Task, result["task_id"])
    assert task is not None
    assert task.title == "Auto: nightly"


def test_cron_due_detection(db_session):
    a = Automation(
        name="hourly",
        trigger_type=AutomationTrigger.cron,
        cron_expr="hourly",
        enabled=True,
        auto_start=False,
    )
    db_session.add(a)
    db_session.commit()
    due = due_cron_automations([a])
    assert due == [a]


def test_run_emits_transcript_events(db_session):
    task = Task(title="Improve search relevance", require_approval=False)
    db_session.add(task)
    db_session.commit()
    run = run_workflow(db_session, task)
    assert run.status == RunStatus.completed
    events = list(db_session.scalars(select(RunEvent).where(RunEvent.run_id == run.id)))
    kinds = {e.kind for e in events}
    assert "run" in kinds
    assert "stage_start" in kinds
    assert "stage_complete" in kinds


def test_analysis_includes_parallel_subagents(db_session):
    task = Task(title="Add CSV export to reports", require_approval=False)
    db_session.add(task)
    db_session.commit()
    run = run_workflow(db_session, task)
    analysis = next(s for s in run.stages if s.name == "analysis")
    assert analysis.output_payload["subagents"]["parallel"] is True


def test_api_environments_secrets_mcp_automations(client):
    env = client.post(
        "/api/environments", json={"name": "ci-env", "update_script": "pnpm install"}
    )
    assert env.status_code == 201
    env_id = env.json()["id"]
    refreshed = client.post(f"/api/environments/{env_id}/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "ready"

    secret = client.post(
        "/api/secrets",
        json={"name": "TOKEN", "value": "super-secret", "scope": "runtime"},
    )
    assert secret.status_code == 201
    assert "super-secret" not in secret.text
    listed = client.get("/api/secrets")
    assert listed.status_code == 200
    assert listed.json()[0]["has_value"] is True

    egress = client.get("/api/egress-policy")
    assert egress.status_code == 200
    check = client.post(
        "/api/egress-policy/check", json={"url": "https://github.com/x/y"}
    )
    assert check.json()["allowed"] is True

    mcp = client.post(
        "/api/mcp/servers",
        json={"name": "docs", "transport": "http", "url": "https://example.com"},
    )
    assert mcp.status_code == 201
    inv = client.post(
        f"/api/mcp/servers/{mcp.json()['id']}/invoke",
        json={"tool": "docs.ping", "arguments": {}},
    )
    assert inv.json()["ok"] is True

    auto = client.post(
        "/api/automations",
        json={
            "name": "hook-me",
            "trigger_type": "webhook",
            "auto_start": False,
            "task_title_template": "From hook {{name}}",
        },
    )
    assert auto.status_code == 201
    token = auto.json()["webhook_token"]
    fired = client.post(f"/api/automations/webhook/{token}", json={"ref": "main"})
    assert fired.status_code == 200
    assert fired.json()["task_id"]


def test_hitl_comments_and_artifact_download(client):
    create = client.post("/api/tasks", json={"title": "Add logout button to navbar"})
    task_id = create.json()["id"]
    run = client.post(f"/api/tasks/{task_id}/runs?sync=true").json()
    run_id = run["id"]

    comment = client.post(
        f"/api/runs/{run_id}/comments",
        json={"body": "Please also update docs", "kind": "comment"},
    )
    assert comment.status_code == 201
    steer = client.post(
        f"/api/runs/{run_id}/steer",
        json={"guidance": "Prefer minimal diff"},
    )
    assert steer.status_code == 201
    events = client.get(f"/api/runs/{run_id}/events")
    assert events.status_code == 200
    assert any(e["kind"] == "hitl" for e in events.json())

    arts = client.get(f"/api/runs/{run_id}/artifacts")
    assert arts.status_code == 200
    report = next(a for a in arts.json() if a["kind"] == "report")
    content = client.get(f"/api/artifacts/{report['id']}/content")
    assert content.status_code == 200
    assert "Report" in content.text or "Spec" in content.text


def test_emit_event_helper(db_session):
    task = Task(title="Emit event fixture task")
    db_session.add(task)
    db_session.commit()
    run = WorkflowRun(task_id=task.id)
    db_session.add(run)
    db_session.commit()
    ev = emit_event(
        db_session, run_id=run.id, kind="info", message="hello", commit=True
    )
    assert ev.id
