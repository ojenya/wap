"""Integration tests for the REST API."""

from __future__ import annotations


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_workflows(client):
    resp = client.get("/api/workflows")
    assert resp.status_code == 200
    assert "core-v1" in resp.json()
    assert resp.json()["core-v1"][0] == "intake"


def test_create_and_run_task_end_to_end(client):
    create = client.post(
        "/api/tasks",
        json={"title": "Add CSV export to reports", "description": "Export table data"},
    )
    assert create.status_code == 201
    task_id = create.json()["id"]

    run = client.post(f"/api/tasks/{task_id}/runs?sync=true")
    assert run.status_code == 201
    body = run.json()
    assert body["status"] == "completed"
    assert len(body["stages"]) == 12
    assert body["artifacts"]

    detail = client.get(f"/api/tasks/{task_id}")
    assert detail.status_code == 200
    assert len(detail.json()["runs"]) == 1


def test_high_risk_awaits_approval(client):
    create = client.post(
        "/api/tasks",
        json={
            "title": "Rotate the auth secret token",
            "description": "Update password encryption keys",
            "require_approval": True,
        },
    )
    task_id = create.json()["id"]
    run = client.post(f"/api/tasks/{task_id}/runs?sync=true").json()
    assert run["status"] == "awaiting_approval"
    approved = client.post(f"/api/runs/{run['id']}/approve?sync=true", json={"note": "lgtm"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "completed"


def test_cancel_run_at_approval_gate(client):
    create = client.post(
        "/api/tasks",
        json={
            "title": "Rotate the auth secret token",
            "description": "Update password encryption keys",
            "require_approval": True,
        },
    )
    task_id = create.json()["id"]
    run = client.post(f"/api/tasks/{task_id}/runs?sync=true").json()
    assert run["status"] == "awaiting_approval"
    cancelled = client.post(f"/api/runs/{run['id']}/cancel")
    assert cancelled.status_code == 200
    body = cancelled.json()
    assert body["status"] == "cancelled"
    assert body["finished_at"]
    events = client.get(f"/api/runs/{run['id']}/events").json()
    assert any("cancelled" in (e.get("message") or "") for e in events)
    # Terminal — second cancel is rejected.
    again = client.post(f"/api/runs/{run['id']}/cancel")
    assert again.status_code == 400


def test_cancel_rejects_completed_run(client):
    create = client.post(
        "/api/tasks",
        json={"title": "Add CSV export to reports", "description": "Export table data"},
    )
    task_id = create.json()["id"]
    run = client.post(f"/api/tasks/{task_id}/runs?sync=true").json()
    assert run["status"] == "completed"
    resp = client.post(f"/api/runs/{run['id']}/cancel")
    assert resp.status_code == 400


def test_task_validation_rejects_short_title(client):
    resp = client.post("/api/tasks", json={"title": "hi"})
    assert resp.status_code == 422


def test_missing_task_returns_404(client):
    assert client.get("/api/tasks/does-not-exist").status_code == 404


def test_metrics_and_workflow_config(client):
    assert client.get("/api/metrics").status_code == 200
    cfg = client.get("/api/workflow-config")
    assert cfg.status_code == 200
    assert "enabled_stages" in cfg.json()["params"]


def test_eval_harness(client):
    resp = client.post("/api/learning/evals/run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert body["passed"] + body["failed"] == body["total"]
