"""ORM models: Repository, Task, WorkflowRun, StageExecution, Artifact."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class RunStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
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


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))
    provider: Mapped[RepoProvider] = mapped_column(Enum(RepoProvider), default=RepoProvider.git)
    default_branch: Mapped[str] = mapped_column(String(200), default="main")
    # Encrypted at rest via app.security.encrypt_secret. Never returned raw.
    token_encrypted: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[RepoStatus] = mapped_column(Enum(RepoStatus), default=RepoStatus.pending)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    tasks: Mapped[list[Task]] = relationship(back_populates="repository")


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
    # Purpose of the run: audit (read-oriented) or develop (change-oriented).
    task_type: Mapped[str] = mapped_column(String(50), default="bug_fix")
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)

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
    kind: Mapped[str] = mapped_column(String(50))  # report | patch | trace | log
    name: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    run: Mapped[WorkflowRun] = relationship(back_populates="artifacts")
