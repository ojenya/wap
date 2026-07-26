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
    vm_instance_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
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


# ---------------------------------------------------------------------------
# Cursor Cloud–inspired platform extensions
# ---------------------------------------------------------------------------


class EnvBackend(enum.StrEnum):
    local = "local"
    firecracker = "firecracker"


class EnvironmentStatus(enum.StrEnum):
    draft = "draft"
    ready = "ready"
    refreshing = "refreshing"
    error = "error"
    booting = "booting"


class SecretScope(enum.StrEnum):
    environment = "environment"
    runtime = "runtime"
    build = "build"


class AutomationTrigger(enum.StrEnum):
    webhook = "webhook"
    cron = "cron"
    gitlab_mr = "gitlab_mr"
    github_pr = "github_pr"
    manual = "manual"


class McpTransport(enum.StrEnum):
    http = "http"
    stdio = "stdio"


class Environment(Base):
    """Per-repo (or shared) cloud-like development environment definition."""

    __tablename__ = "environments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    repository_id: Mapped[str | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
    )
    dockerfile_path: Mapped[str] = mapped_column(String(500), default=".cursor/Dockerfile")
    environment_json_path: Mapped[str] = mapped_column(
        String(500), default=".cursor/environment.json"
    )
    update_script: Mapped[str] = mapped_column(Text, default="pnpm install\npip install -e .")
    agents_md_path: Mapped[str] = mapped_column(String(500), default="AGENTS.md")
    # Prefer Firecracker; manager falls back to local when KVM/binary missing.
    backend: Mapped[EnvBackend] = mapped_column(
        Enum(EnvBackend), default=EnvBackend.firecracker
    )
    vcpu_count: Mapped[int] = mapped_column(Integer, default=2)
    mem_size_mib: Mapped[int] = mapped_column(Integer, default=1024)
    snapshot_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[EnvironmentStatus] = mapped_column(
        Enum(EnvironmentStatus), default=EnvironmentStatus.draft
    )
    last_refresh_log: Mapped[str] = mapped_column(Text, default="")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class VaultSecret(Base):
    """Scoped encrypted secret (never returned in plaintext via API)."""

    __tablename__ = "vault_secrets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    scope: Mapped[SecretScope] = mapped_column(Enum(SecretScope), default=SecretScope.runtime)
    environment_id: Mapped[str | None] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"), nullable=True
    )
    value_encrypted: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class EgressPolicy(Base):
    """Network egress allowlist for agent runs (Cursor-like)."""

    __tablename__ = "egress_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), unique=True, default="default")
    allow_all: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_domains: Mapped[list] = mapped_column(JSON, default=list)
    environment_id: Mapped[str | None] = mapped_column(
        ForeignKey("environments.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class RunEvent(Base):
    """Append-only transcript / observability timeline for a run."""

    __tablename__ = "run_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(50), default="info")
    stage_name: Mapped[str] = mapped_column(String(100), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class RunComment(Base):
    """Human-in-the-loop comments / steering notes on a run."""

    __tablename__ = "run_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id", ondelete="CASCADE"))
    author: Mapped[str] = mapped_column(String(100), default="operator")
    body: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(50), default="comment")  # comment|approval|steer
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Automation(Base):
    """Event-driven task factory (webhook / cron / SCM triggers)."""

    __tablename__ = "automations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    trigger_type: Mapped[AutomationTrigger] = mapped_column(
        Enum(AutomationTrigger), default=AutomationTrigger.webhook
    )
    cron_expr: Mapped[str] = mapped_column(String(100), default="")
    webhook_token: Mapped[str] = mapped_column(String(64), default="")
    repository_id: Mapped[str | None] = mapped_column(
        ForeignKey("repositories.id", ondelete="SET NULL"), nullable=True
    )
    task_title_template: Mapped[str] = mapped_column(String(200), default="Automation: {{name}}")
    task_description_template: Mapped[str] = mapped_column(Text, default="")
    task_type: Mapped[str] = mapped_column(String(50), default="bug_fix")
    auto_start: Mapped[bool] = mapped_column(Boolean, default=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class McpServer(Base):
    """Registered MCP server (HTTP or stdio) available to agents."""

    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    transport: Mapped[McpTransport] = mapped_column(Enum(McpTransport), default=McpTransport.http)
    url: Mapped[str] = mapped_column(String(500), default="")
    command: Mapped[str] = mapped_column(String(500), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    tools_cache: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class VmStatus(enum.StrEnum):
    creating = "creating"
    running = "running"
    paused = "paused"
    snapshotting = "snapshotting"
    restoring = "restoring"
    stopped = "stopped"
    error = "error"
    destroyed = "destroyed"


class VmInstance(Base):
    """Booted microVM (Firecracker) or local jail bound to an Environment."""

    __tablename__ = "vm_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    environment_id: Mapped[str] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE")
    )
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    backend: Mapped[EnvBackend] = mapped_column(Enum(EnvBackend), default=EnvBackend.local)
    status: Mapped[VmStatus] = mapped_column(Enum(VmStatus), default=VmStatus.creating)
    # Host paths for the instance workspace / socket / snapshot.
    work_dir: Mapped[str] = mapped_column(String(1000), default="")
    socket_path: Mapped[str] = mapped_column(String(1000), default="")
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    guest_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapshot_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    rootfs_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Worktree bind/mount target inside the VM (or local workspace).
    workspace_path: Mapped[str] = mapped_column(String(1000), default="")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
