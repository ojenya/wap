"""ORM models for the multi-agent change factory."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class RunStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"


class StageStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class RiskLevel(enum.StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class RepoProvider(enum.StrEnum):
    gitlab = "gitlab"
    github = "github"
    git = "git"


class RepoStatus(enum.StrEnum):
    pending = "pending"
    ready = "ready"
    error = "error"


class UserRole(enum.StrEnum):
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))
    provider: Mapped[RepoProvider] = mapped_column(Enum(RepoProvider), default=RepoProvider.git)
    default_branch: Mapped[str] = mapped_column(String(200), default="main")
    token_encrypted: Mapped[str] = mapped_column(Text, default="")
    # GitLab numeric project id when known (enables MR creation / project APIs).
    gitlab_project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Monorepo scope: only these path prefixes are indexed / mutable.
    path_filters: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[RepoStatus] = mapped_column(Enum(RepoStatus), default=RepoStatus.pending)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    tasks: Mapped[list[Task]] = relationship(back_populates="repository")
    chunks: Mapped[list[CodeChunk]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    repository_id: Mapped[str | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
    )
    repo_url: Mapped[str] = mapped_column(String(500), default="")
    base_branch: Mapped[str] = mapped_column(String(200), default="main")
    task_type: Mapped[str] = mapped_column(String(50), default="bug_fix")
    # Optional per-task path scope (intersects with repository.path_filters).
    path_filters: Mapped[list] = mapped_column(JSON, default=list)
    # When true and risk=high, develop waits for explicit approval.
    require_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    repository: Mapped[Repository | None] = relationship(back_populates="tasks")
    runs: Mapped[list[WorkflowRun]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="WorkflowRun.created_at"
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    workflow_version: Mapped[str] = mapped_column(String(50), default="core-v1")
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.pending)
    risk_level: Mapped[RiskLevel | None] = mapped_column(Enum(RiskLevel), nullable=True)
    worktree_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Resume cursor for paused / retrying runs (stage index).
    resume_from_index: Mapped[int] = mapped_column(Integer, default=0)
    develop_iterations: Mapped[int] = mapped_column(Integer, default=0)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mr_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_duration_ms: Mapped[float] = mapped_column(Float, default=0.0)

    task: Mapped[Task] = relationship(back_populates="runs")
    stages: Mapped[list[StageExecution]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="StageExecution.order_index"
    )
    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Artifact.created_at"
    )


class StageExecution(Base):
    __tablename__ = "stage_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    agent_role: Mapped[str] = mapped_column(String(100))
    status: Mapped[StageStatus] = mapped_column(Enum(StageStatus), default=StageStatus.pending)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    output_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    run: Mapped[WorkflowRun] = relationship(back_populates="stages")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    run: Mapped[WorkflowRun] = relationship(back_populates="artifacts")


class CodeChunk(Base):
    """Indexed code/doc chunk for RAG v1 (SQLite FTS companion)."""

    __tablename__ = "code_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(500))
    symbol: Mapped[str] = mapped_column(String(200), default="")
    language: Mapped[str] = mapped_column(String(50), default="")
    start_line: Mapped[int] = mapped_column(Integer, default=1)
    end_line: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text, default="")
    commit_sha: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    repository: Mapped[Repository] = relationship(back_populates="chunks")


class CaseMemory(Base):
    """Validated lessons from completed runs (learning loop)."""

    __tablename__ = "case_memory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_type: Mapped[str] = mapped_column(String(50), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    lesson: Mapped[str] = mapped_column(Text, default="")
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class EvalCase(Base):
    """Regression eval suite entry."""

    __tablename__ = "eval_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    task_title: Mapped[str] = mapped_column(String(200))
    task_description: Mapped[str] = mapped_column(Text, default="")
    task_type: Mapped[str] = mapped_column(String(50), default="bug_fix")
    expect_risk: Mapped[str | None] = mapped_column(String(20), nullable=True)
    expect_status: Mapped[str] = mapped_column(String(40), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class WorkflowConfig(Base):
    """Versioned safe workflow parameters (not arbitrary graph edits)."""

    __tablename__ = "workflow_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, default="default")
    version: Mapped[str] = mapped_column(String(50), default="core-v1")
    # Safe knobs only: enabled stages, budgets, checks, models, gates.
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ApiUser(Base):
    __tablename__ = "api_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100))
    api_key_hash: Mapped[str] = mapped_column(String(128), unique=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.operator)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=120)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SecretAccessLog(Base):
    __tablename__ = "secret_access_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    repository_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    purpose: Mapped[str] = mapped_column(String(100))
    actor: Mapped[str] = mapped_column(String(100), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
