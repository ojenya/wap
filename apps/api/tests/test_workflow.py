"""Unit tests for the deterministic workflow engine."""

from __future__ import annotations

from app.models import RunStatus, StageStatus, Task
from app.workflow.engine import run_workflow
from app.workflow.registry import WORKFLOWS, build_workflow


def test_workflow_definition_is_ordered_lifecycle():
    stages = [s.name for s in build_workflow("core-v1")]
    assert stages[0] == "intake"
    assert stages[-1] == "learning"
    assert "develop" in stages and "review" in stages and "report" in stages


def test_run_completes_all_stages(db_session):
    task = Task(title="Add logout button to navbar", description="Users need a way to log out")
    db_session.add(task)
    db_session.commit()

    run = run_workflow(db_session, task)

    assert run.status == RunStatus.completed
    assert len(run.stages) == len(WORKFLOWS["core-v1"])
    assert all(s.status == StageStatus.completed for s in run.stages)
    assert run.total_tokens > 0


def test_high_risk_task_flags_human_gate(db_session):
    task = Task(title="Rotate the auth secret token", description="Update password encryption")
    db_session.add(task)
    db_session.commit()

    run = run_workflow(db_session, task)

    intake = next(s for s in run.stages if s.name == "intake")
    audit = next(s for s in run.stages if s.name == "audit")
    assert intake.output_payload["risk_level"] == "high"
    assert audit.output_payload["requires_human_gate"] is True
    assert "security_scan" in intake.output_payload["required_checks"]


def test_report_and_patch_artifacts_are_created(db_session):
    task = Task(title="Fix pagination bug on dashboard")
    db_session.add(task)
    db_session.commit()

    run = run_workflow(db_session, task)

    kinds = {a.kind for a in run.artifacts}
    assert "report" in kinds
    assert "patch" in kinds
    report = next(a for a in run.artifacts if a.kind == "report")
    assert "Spec compliance" in report.content


def test_stage_trace_is_persisted_with_evidence(db_session):
    task = Task(title="Improve search relevance")
    db_session.add(task)
    db_session.commit()

    run = run_workflow(db_session, task)

    rag = next(s for s in run.stages if s.name == "repository_context")
    assert rag.evidence, "RAG stage should cite retrieved files"
    assert rag.duration_ms >= 0
