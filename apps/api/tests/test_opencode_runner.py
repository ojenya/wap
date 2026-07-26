"""Tests for the opencode runner adapter (Zen/Go orientation + safe fallback)."""

from __future__ import annotations

from app.config import Settings
from app.models import Task
from app.workflow.engine import run_workflow
from app.workflow.opencode_runner import OpencodeRequest, OpencodeRunner


def test_unavailable_without_api_key():
    runner = OpencodeRunner(Settings(opencode_api_key=""))
    assert runner.is_available() is False
    result = runner.run(OpencodeRequest(task_title="anything"))
    assert result.mode == "unavailable"
    assert result.available is False


def test_config_orients_to_zen_base_url_by_default():
    runner = OpencodeRunner(Settings(opencode_api_key="k"))
    cfg = runner.build_config()
    assert cfg["provider"]["opencode"]["options"]["baseURL"] == "https://opencode.ai/zen/v1"
    assert cfg["agent"]["build"]["permission"]["edit"] == "allow"


def test_config_orients_to_go_base_url():
    runner = OpencodeRunner(Settings(opencode_plan="go", opencode_api_key="k"))
    cfg = runner.build_config()
    assert cfg["provider"]["opencode"]["options"]["baseURL"] == "https://opencode.ai/zen/go/v1"
    assert runner.settings.opencode_base_url == "https://opencode.ai/zen/go/v1"


def test_develop_stage_falls_back_to_stub_and_reports_runner(db_session):
    task = Task(title="Add CSV export to reports")
    db_session.add(task)
    db_session.commit()

    run = run_workflow(db_session, task)

    develop = next(s for s in run.stages if s.name == "develop")
    runner_info = develop.output_payload["runner"]
    # No opencode CLI/key in the test env -> unavailable -> deterministic stub.
    assert runner_info["mode"] == "unavailable"
    assert runner_info["plan"] == "zen"
    assert develop.output_payload["diff"], "stub patch should still be produced"
