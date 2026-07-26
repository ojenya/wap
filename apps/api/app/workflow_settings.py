"""Versioned safe workflow parameters (hybrid editable config)."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WorkflowConfig

# Only these keys are editable from the UI / API. Arbitrary graph edits are denied.
SAFE_PARAM_DEFAULTS: dict = {
    "enabled_stages": [
        "intake",
        "repository_context",
        "audit",
        "analysis",
        "spec",
        "approval_gate",
        "develop",
        "static_checks",
        "sandbox_qa",
        "review",
        "report",
        "learning",
    ],
    "required_checks": ["lint", "typecheck", "unit_tests"],
    "max_develop_iterations": 3,
    "auto_approve_low_risk": True,
    "auto_approve_high_risk": False,
    "create_merge_request": True,
    "playwright_enabled": True,
    # When true, sandbox_qa may not skip: missing worktree/Chromium fails the run.
    "playwright_required": True,
    "opencode_plan": "zen",
    "opencode_model": "opencode/qwen3-coder",
    "report_sections": [
        "executive_summary",
        "scope",
        "spec_compliance",
        "static_checks",
        "cost",
    ],
}

ALLOWED_KEYS = set(SAFE_PARAM_DEFAULTS)


def get_or_create_config(db: Session, name: str = "default") -> WorkflowConfig:
    cfg = db.scalar(select(WorkflowConfig).where(WorkflowConfig.name == name))
    if cfg:
        return cfg
    cfg = WorkflowConfig(name=name, version="core-v1", params=deepcopy(SAFE_PARAM_DEFAULTS))
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def update_config(db: Session, name: str, params: dict) -> WorkflowConfig:
    cfg = get_or_create_config(db, name)
    cleaned = {k: v for k, v in params.items() if k in ALLOWED_KEYS}
    merged = deepcopy(SAFE_PARAM_DEFAULTS)
    merged.update(cfg.params or {})
    merged.update(cleaned)
    # Policy: never allow enabling unknown stages beyond the core list.
    core = set(SAFE_PARAM_DEFAULTS["enabled_stages"])
    enabled = [s for s in merged.get("enabled_stages", []) if s in core]
    if "intake" not in enabled:
        enabled.insert(0, "intake")
    if "report" not in enabled:
        enabled.append("report")
    merged["enabled_stages"] = enabled
    cfg.params = merged
    cfg.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(cfg)
    return cfg


def effective_params(db: Session | None = None) -> dict:
    if db is None:
        return deepcopy(SAFE_PARAM_DEFAULTS)
    cfg = get_or_create_config(db)
    merged = deepcopy(SAFE_PARAM_DEFAULTS)
    merged.update(cfg.params or {})
    return merged
