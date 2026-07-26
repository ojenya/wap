"""Cooperative run cancellation between stages."""

from __future__ import annotations

import threading

from sqlalchemy.orm import sessionmaker

from app.models import RunStatus, StageStatus, Task, WorkflowRun
from app.workflow import stages as stage_mod
from app.workflow.engine import cancel_run, execute_run


def test_cancel_stops_after_current_stage(db_session, monkeypatch):
    """Cancel mid-run: in-flight stage may finish; later stages are skipped."""
    started = threading.Event()
    release = threading.Event()
    original = stage_mod.AnalysisStage.run

    def slow_analysis(self, context):  # noqa: ANN001
        started.set()
        assert release.wait(timeout=5)
        return original(self, context)

    monkeypatch.setattr(stage_mod.AnalysisStage, "run", slow_analysis)

    task = Task(
        title="Cancel mid workflow please",
        description="Need enough text for intake",
        task_type="bug_fix",
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    run = WorkflowRun(task_id=task.id, status=RunStatus.pending)
    db_session.add(run)
    db_session.commit()
    task_id, run_id = task.id, run.id

    Session = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)

    def worker() -> None:
        session = Session()
        try:
            t = session.get(Task, task_id)
            r = session.get(WorkflowRun, run_id)
            assert t and r
            execute_run(session, r, t)
        finally:
            session.close()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    assert started.wait(timeout=5)

    other = Session()
    try:
        active = other.get(WorkflowRun, run_id)
        assert active is not None
        cancel_run(other, active, actor="tester")
        assert active.status == RunStatus.cancelled
    finally:
        other.close()

    release.set()
    thread.join(timeout=15)
    assert not thread.is_alive()

    db_session.expire_all()
    final = db_session.get(WorkflowRun, run_id)
    assert final is not None
    assert final.status == RunStatus.cancelled
    by_name = {s.name: s for s in final.stages}
    assert "analysis" in by_name
    for name in ("spec", "develop", "report"):
        if name in by_name:
            assert by_name[name].status == StageStatus.skipped


def test_execute_run_respects_pre_cancel(db_session):
    task = Task(title="Already cancelled before start", description="desc text here")
    db_session.add(task)
    db_session.commit()

    run = WorkflowRun(task_id=task.id, status=RunStatus.cancelled)
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    out = execute_run(db_session, run, task)
    assert out.status == RunStatus.cancelled
    assert all(s.status != StageStatus.completed for s in out.stages)
