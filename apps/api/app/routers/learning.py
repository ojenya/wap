"""Case memory + regression eval harness."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Admin, Operator, Viewer
from app.db import get_db
from app.models import CaseMemory, EvalCase, Task
from app.schemas import CaseMemoryOut, EvalCaseIn, EvalCaseOut
from app.workflow.engine import run_workflow

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/cases", response_model=list[CaseMemoryOut])
def list_cases(_: Viewer, db: Session = Depends(get_db)) -> list[CaseMemory]:
    return list(db.scalars(select(CaseMemory).order_by(CaseMemory.created_at.desc()).limit(100)))


@router.get("/evals", response_model=list[EvalCaseOut])
def list_evals(_: Viewer, db: Session = Depends(get_db)) -> list[EvalCase]:
    return list(db.scalars(select(EvalCase).order_by(EvalCase.created_at.desc())))


@router.post("/evals", response_model=EvalCaseOut, status_code=201)
def create_eval(payload: EvalCaseIn, _: Admin, db: Session = Depends(get_db)) -> EvalCase:
    row = EvalCase(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/evals/run")
def run_evals(_: Operator, db: Session = Depends(get_db)) -> dict:
    """Run the regression suite synchronously and return pass/fail per case."""
    cases = list(db.scalars(select(EvalCase)))
    if not cases:
        # Seed a minimal default suite on first run.
        cases = [
            EvalCase(
                name="low-risk-feature",
                task_title="Add CSV export",
                task_description="export tables",
                task_type="feature",
                expect_risk="low",
                expect_status="completed",
            ),
            EvalCase(
                name="high-risk-auth",
                task_title="Rotate auth secret token",
                task_description="Update password encryption",
                task_type="audit",
                expect_risk="high",
                expect_status="completed",
            ),
        ]
        for c in cases:
            db.add(c)
        db.commit()
        for c in cases:
            db.refresh(c)

    results = []
    passed = 0
    for case in cases:
        task = Task(
            title=case.task_title,
            description=case.task_description,
            task_type=case.task_type,
            require_approval=False,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        # Force auto-approve path for evals.
        run = run_workflow(db, task)
        risk_ok = case.expect_risk is None or (
            run.risk_level is not None and run.risk_level.value == case.expect_risk
        )
        status_ok = run.status.value == case.expect_status
        ok = bool(risk_ok and status_ok)
        if ok:
            passed += 1
        results.append(
            {
                "case": case.name,
                "ok": ok,
                "status": run.status.value,
                "risk": run.risk_level.value if run.risk_level else None,
                "tokens": run.total_tokens,
            }
        )
    failed = len(results) - passed
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
    }


@router.delete("/evals/{case_id}", status_code=204)
def delete_eval(case_id: str, _: Admin, db: Session = Depends(get_db)) -> None:
    row = db.get(EvalCase, case_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Eval case not found")
    db.delete(row)
    db.commit()
