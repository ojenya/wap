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

    run = client.post(f"/api/tasks/{task_id}/runs")
    assert run.status_code == 201
    body = run.json()
    assert body["status"] == "completed"
    assert len(body["stages"]) == 12
    assert body["artifacts"]

    detail = client.get(f"/api/tasks/{task_id}")
    assert detail.status_code == 200
    assert len(detail.json()["runs"]) == 1


def test_task_validation_rejects_short_title(client):
    resp = client.post("/api/tasks", json={"title": "hi"})
    assert resp.status_code == 422


def test_missing_task_returns_404(client):
    assert client.get("/api/tasks/does-not-exist").status_code == 404
