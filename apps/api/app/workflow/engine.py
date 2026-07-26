"""Workflow engine: async-capable, pausable at approval, with develop retry loop."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.environments import environment_for_repository
from app.events import emit_event
from app.git_workspace import GitWorkspaceError, GitWorkspaceManager, authenticated_url
from app.github_client import GitHubError, create_pull_request, parse_github_repo, post_pr_comment
from app.gitlab_client import GitLabError, create_merge_request, post_mr_note, push_branch
from app.models import (
    Artifact,
    RepoProvider,
    Repository,
    RepoStatus,
    RiskLevel,
    RunStatus,
    StageExecution,
    StageStatus,
    Task,
    WorkflowRun,
)
from app.rag import index_worktree
from app.security import reveal_repo_token
from app.vm.backends import VmBackendError
from app.vm.manager import VmManager
from app.workflow.contracts import StageOutcome, TaskInput, WorkflowContext
from app.workflow.registry import DEFAULT_WORKFLOW, build_workflow
from app.workflow_settings import effective_params


def _now() -> datetime:
    return datetime.now(UTC)


def start_workflow_async(task_id: str, version: str = DEFAULT_WORKFLOW) -> str:
    """Create a pending run and execute it on a background thread. Returns run id."""
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if task is None:
            raise ValueError("Task not found")
        run = WorkflowRun(
            task_id=task.id,
            workflow_version=version,
            status=RunStatus.pending,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
    finally:
        db.close()

    thread = threading.Thread(
        target=_thread_run, args=(run_id,), name=f"workflow-{run_id[:8]}", daemon=True
    )
    thread.start()
    return run_id


def _thread_run(run_id: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(WorkflowRun, run_id)
        if run is None:
            return
        task = db.get(Task, run.task_id)
        if task is None:
            run.status = RunStatus.failed
            run.finished_at = _now()
            db.commit()
            return
        execute_run(db, run, task)
    finally:
        db.close()


def run_workflow(db: Session, task: Task, version: str = DEFAULT_WORKFLOW) -> WorkflowRun:
    """Synchronous helper used by tests: create + execute in the current thread."""
    run = WorkflowRun(task_id=task.id, workflow_version=version, status=RunStatus.pending)
    db.add(run)
    db.commit()
    db.refresh(run)
    return execute_run(db, run, task)


def approve_run(
    db: Session, run: WorkflowRun, actor: str = "operator", *, sync: bool = False
) -> WorkflowRun:
    """Resume a run paused at the approval gate."""
    if run.status != RunStatus.awaiting_approval:
        raise ValueError("Run is not awaiting approval")
    run.approved_by = actor
    run.approved_at = _now()
    run.status = RunStatus.running
    # Mark approval_gate stage completed with approved=true for resume context.
    gate = next((s for s in run.stages if s.name == "approval_gate"), None)
    if gate:
        gate.status = StageStatus.completed
        gate.output_payload = {
            **(gate.output_payload or {}),
            "approved": True,
            "decision": f"approved by {actor}",
            "gate_required": True,
        }
        gate.finished_at = _now()
        run.resume_from_index = gate.order_index + 1
    db.commit()

    task = db.get(Task, run.task_id)
    assert task is not None

    if sync:
        return execute_run(db, run, task, resume=True)

    run_id = run.id

    def _resume() -> None:
        session = SessionLocal()
        try:
            r = session.get(WorkflowRun, run_id)
            t = session.get(Task, r.task_id) if r else None
            if r and t:
                execute_run(session, r, t, resume=True)
        finally:
            session.close()

    threading.Thread(target=_resume, name=f"resume-{run_id[:8]}", daemon=True).start()
    db.refresh(run)
    return run


def execute_run(
    db: Session, run: WorkflowRun, task: Task, resume: bool = False
) -> WorkflowRun:
    params = effective_params(db)
    run.status = RunStatus.running
    emit_event(
        db,
        run_id=run.id,
        kind="run",
        message="run started" if not resume else "run resumed",
        payload={"resume": resume, "workflow": run.workflow_version},
    )
    db.commit()

    worktree_path = run.worktree_path or ""
    head_sha = ""
    repo_url = task.repo_url
    repo: Repository | None = None

    if task.repository_id and not worktree_path:
        repo = db.get(Repository, task.repository_id)
        if repo is None:
            return _fail(db, run, "Repository not found")
        repo_url = repo.url
        try:
            info = GitWorkspaceManager().create_worktree(
                repo, run_id=run.id, branch=task.base_branch or repo.default_branch, db=db
            )
            worktree_path = str(info.path)
            head_sha = info.head_sha
            run.worktree_path = worktree_path
            repo.status = RepoStatus.ready
            repo.head_sha = head_sha
            repo.last_synced_at = _now()
            repo.last_error = None
            db.commit()
            # Index for RAG v1.
            filters = list(repo.path_filters or []) + list(task.path_filters or [])
            index_worktree(
                db, repo, Path(worktree_path), commit_sha=head_sha, path_filters=filters or None
            )
        except GitWorkspaceError as exc:
            if repo:
                repo.status = RepoStatus.error
                repo.last_error = str(exc)
            return _fail(db, run, f"worktree: {exc}", stage_name="worktree")
    elif worktree_path:
        head_sha = ""
        try:
            from app.git_workspace import _run

            head_sha = _run(["git", "rev-parse", "HEAD"], cwd=Path(worktree_path))
        except Exception:  # noqa: BLE001
            pass
        if task.repository_id:
            repo = db.get(Repository, task.repository_id)

    path_filters = list(task.path_filters or [])
    if repo and repo.path_filters:
        # Intersection semantics when both set; else repo filters.
        path_filters = path_filters or list(repo.path_filters)

    # Boot Firecracker/local VM for the repository environment when configured.
    vm_instance_id = run.vm_instance_id or ""
    vm_backend = ""
    if worktree_path and not resume:
        env = environment_for_repository(db, task.repository_id)
        if env and params.get("vm_enabled", True):
            try:
                manager = VmManager(db)
                vm = manager.boot(
                    env,
                    run_id=run.id,
                    workspace_src=worktree_path,
                    restore_snapshot=bool(env.snapshot_id),
                )
                vm_instance_id = vm.id
                vm_backend = vm.backend.value
                run.vm_instance_id = vm.id
                # Stages operate on the VM workspace mirror.
                worktree_path = vm.workspace_path
                run.worktree_path = worktree_path
                emit_event(
                    db,
                    run_id=run.id,
                    kind="vm",
                    message=f"booted {vm_backend} vm {vm.id}",
                    payload={
                        "vm_instance_id": vm.id,
                        "backend": vm_backend,
                        "emulated": bool((vm.meta or {}).get("emulated")),
                        "workspace_path": vm.workspace_path,
                    },
                )
                db.commit()
            except VmBackendError as exc:
                emit_event(
                    db,
                    run_id=run.id,
                    kind="vm_error",
                    message=str(exc),
                )
                db.commit()

    context = WorkflowContext(
        task=TaskInput(
            id=task.id,
            title=task.title,
            description=task.description,
            repo_url=repo_url,
            base_branch=task.base_branch,
            task_type=task.task_type,
            repository_id=task.repository_id,
            path_filters=path_filters,
            require_approval=task.require_approval,
        ),
        run_id=run.id,
        worktree_path=worktree_path or "",
        vm_instance_id=vm_instance_id,
        vm_backend=vm_backend,
        head_sha=head_sha,
        workflow_params=params,
    )

    # Rebuild prior outputs when resuming.
    if resume:
        for stage_row in sorted(run.stages, key=lambda s: s.order_index):
            if stage_row.status == StageStatus.completed:
                context.outputs[stage_row.name] = stage_row.output_payload or {}

    stages = build_workflow(run.workflow_version)
    enabled = set(params.get("enabled_stages") or [s.name for s in stages])
    start_index = run.resume_from_index if resume else 0
    max_iters = int(params.get("max_develop_iterations") or 3)
    failed = False
    idx = start_index

    while idx < len(stages):
        stage = stages[idx]

        if stage.name not in enabled:
            _record_skipped(db, run, idx, stage.name, stage.agent_role)
            idx += 1
            continue

        # Reuse existing row when retrying/resuming the same index.
        execution = next((s for s in run.stages if s.order_index == idx), None)
        if execution is None:
            execution = StageExecution(
                run_id=run.id,
                order_index=idx,
                name=stage.name,
                agent_role=stage.agent_role,
            )
            db.add(execution)

        if failed:
            execution.status = StageStatus.skipped
            db.commit()
            idx += 1
            continue

        execution.status = StageStatus.running
        execution.started_at = _now()
        execution.input_payload = context.model_dump(mode="json")
        execution.error = None
        emit_event(
            db,
            run_id=run.id,
            kind="stage_start",
            stage_name=stage.name,
            message=f"stage {stage.name} started",
            payload={"agent_role": stage.agent_role},
        )
        db.commit()

        t0 = time.perf_counter()
        try:
            result = stage.run(context)
        except Exception as exc:  # noqa: BLE001
            execution.status = StageStatus.failed
            execution.error = str(exc)
            execution.finished_at = _now()
            execution.duration_ms = (time.perf_counter() - t0) * 1000
            run.total_duration_ms += execution.duration_ms
            emit_event(
                db,
                run_id=run.id,
                kind="stage_error",
                stage_name=stage.name,
                message=str(exc),
            )
            db.commit()
            failed = True
            idx += 1
            continue

        execution.duration_ms = (time.perf_counter() - t0) * 1000
        run.total_duration_ms += execution.duration_ms
        execution.finished_at = _now()
        execution.output_payload = {**result.output, "_tokens": result.tokens}
        execution.evidence = [e.model_dump() for e in result.evidence]
        execution.tokens = result.tokens
        run.total_tokens += result.tokens

        if result.outcome == StageOutcome.awaiting_approval:
            execution.status = StageStatus.running
            execution.output_payload = result.output
            run.status = RunStatus.awaiting_approval
            run.resume_from_index = idx
            db.commit()
            db.refresh(run)
            return run

        if result.outcome == StageOutcome.failed:
            execution.status = StageStatus.failed
            execution.error = result.error
            # Retry loop: static/sandbox failure -> back to develop.
            # Do NOT retry when Playwright never executed (missing worktree /
            # Chromium / disabled) — develop cannot fix infra prerequisites.
            sandbox_infra_gap = stage.name == "sandbox_qa" and result.output.get(
                "mode"
            ) in {"skipped", "disabled"}
            if (
                stage.name in {"static_checks", "sandbox_qa"}
                and not sandbox_infra_gap
                and run.develop_iterations < max_iters
                and "develop" in enabled
                and context.task.task_type != "audit"
            ):
                run.develop_iterations += 1
                db.commit()
                develop_idx = next(i for i, s in enumerate(stages) if s.name == "develop")
                # Invalidate develop..current outputs for a clean retry.
                for name in list(context.outputs):
                    if name in {"develop", "static_checks", "sandbox_qa", "review", "report"}:
                        del context.outputs[name]
                idx = develop_idx
                continue
            failed = True
        else:
            execution.status = StageStatus.completed
            context.outputs[stage.name] = result.output
            _capture_artifacts(db, run, stage.name, result.output)
            emit_event(
                db,
                run_id=run.id,
                kind="stage_complete",
                stage_name=stage.name,
                message=f"stage {stage.name} completed",
                payload={"tokens": result.tokens, "outcome": result.outcome.value},
            )

        db.commit()
        idx += 1

    # Optional MR/PR creation after successful develop (non-audit).
    if (
        not failed
        and params.get("create_merge_request", True)
        and repo
        and context.task.task_type != "audit"
        and context.get("develop").get("branch")
        and worktree_path
    ):
        try:
            if repo.provider == RepoProvider.gitlab and repo.gitlab_project_id:
                _publish_mr(db, run, task, repo, context)
            elif repo.provider == RepoProvider.github:
                _publish_github_pr(db, run, task, repo, context, params)
        except (GitLabError, GitHubError, ValueError, OSError) as exc:
            db.add(
                Artifact(
                    run_id=run.id,
                    kind="log",
                    name="mr-error.log",
                    content=str(exc),
                )
            )
            emit_event(
                db,
                run_id=run.id,
                kind="scm_error",
                message=str(exc),
            )
            db.commit()

    # Snapshot + destroy VM after the run (keeps env.snapshot_id warm).
    if run.vm_instance_id and params.get("vm_destroy_after_run", True):
        try:
            bound_env = environment_for_repository(db, task.repository_id)
            manager = VmManager(db)
            active_vm = manager.get_instance(run.vm_instance_id)
            if bound_env and active_vm and active_vm.status.value == "running":
                if params.get("vm_snapshot_after_run", True):
                    manager.snapshot(active_vm, bound_env)
                manager.destroy(active_vm, bound_env)
                emit_event(
                    db,
                    run_id=run.id,
                    kind="vm",
                    message=f"destroyed vm {active_vm.id}",
                    payload={"vm_instance_id": active_vm.id},
                )
        except VmBackendError as exc:
            emit_event(db, run_id=run.id, kind="vm_error", message=str(exc))

    intake = context.outputs.get("intake", {})
    if intake.get("risk_level"):
        run.risk_level = RiskLevel(intake["risk_level"])
    run.status = RunStatus.failed if failed else RunStatus.completed
    run.finished_at = _now()
    run.resume_from_index = idx
    emit_event(
        db,
        run_id=run.id,
        kind="run",
        message=f"run {run.status.value}",
        payload={"status": run.status.value, "tokens": run.total_tokens},
    )
    db.commit()
    db.refresh(run)
    return run


def _artifact_summary_markdown(run: WorkflowRun) -> str:
    lines = ["## Artifacts", ""]
    for art in run.artifacts:
        if art.kind == "playwright":
            lines.append(f"- Playwright: `{art.name}` → `{art.content}`")
        elif art.kind == "report":
            lines.append(f"- Report: `{art.name}`")
        elif art.kind == "patch":
            lines.append(f"- Patch: `{art.name}`")
    if len(lines) == 2:
        lines.append("_No binary artifacts recorded._")
    return "\n".join(lines)


def _publish_github_pr(
    db: Session,
    run: WorkflowRun,
    task: Task,
    repo: Repository,
    context: WorkflowContext,
    params: dict,
) -> None:
    token = reveal_repo_token(
        db,
        repository_id=repo.id,
        token_encrypted=repo.token_encrypted,
        purpose="push_and_create_pr",
        actor="workflow-engine",
    )
    if not token:
        raise ValueError("Repository has no token for PR creation")
    parsed = parse_github_repo(repo.url)
    if not parsed:
        raise ValueError(f"Cannot parse GitHub owner/repo from {repo.url}")
    owner, name = parsed
    branch = context.get("develop")["branch"]
    remote = authenticated_url(repo.url, token)
    push_branch(context.worktree_path, remote, branch)
    report = ""
    art = next((a for a in run.artifacts if a.kind == "report"), None)
    if art:
        report = art.content
    body = (report or task.description or task.title) + "\n\n" + _artifact_summary_markdown(run)
    pr = create_pull_request(
        token,
        owner,
        name,
        title=f"[Change Factory] {task.title}",
        head=branch,
        base=task.base_branch or repo.default_branch,
        body=body[:60000],
        draft=bool(params.get("github_draft_pr", True)),
    )
    run.mr_url = pr.get("html_url")
    if pr.get("number") is not None:
        post_pr_comment(
            token,
            owner,
            name,
            int(pr["number"]),
            body=f"Automated run `{run.id}` finished.\n\n{_artifact_summary_markdown(run)}",
        )
    db.add(
        Artifact(
            run_id=run.id,
            kind="log",
            name="pull-request.json",
            content=str(pr),
        )
    )
    emit_event(
        db,
        run_id=run.id,
        kind="scm",
        message=f"GitHub PR created: {run.mr_url}",
        payload={"provider": "github", "draft": bool(params.get("github_draft_pr", True))},
    )
    db.commit()


def _publish_mr(
    db: Session, run: WorkflowRun, task: Task, repo: Repository, context: WorkflowContext
) -> None:
    token = reveal_repo_token(
        db,
        repository_id=repo.id,
        token_encrypted=repo.token_encrypted,
        purpose="push_and_create_mr",
        actor="workflow-engine",
    )
    if not token:
        raise ValueError("Repository has no token for MR creation")
    branch = context.get("develop")["branch"]
    remote = authenticated_url(repo.url, token)
    push_branch(context.worktree_path, remote, branch)
    report = ""
    art = next((a for a in run.artifacts if a.kind == "report"), None)
    if art:
        report = art.content
    mr = create_merge_request(
        token,
        repo.gitlab_project_id,  # type: ignore[arg-type]
        source_branch=branch,
        target_branch=task.base_branch or repo.default_branch,
        title=f"[Change Factory] {task.title}",
        description=report or task.description or task.title,
    )
    run.mr_url = mr.get("web_url")
    if mr.get("iid") is not None:
        note = (
            f"Automated run `{run.id}` finished with status **{run.status}**.\n\n"
            f"{report[:4000]}"
        )
        post_mr_note(
            token,
            repo.gitlab_project_id,  # type: ignore[arg-type]
            int(mr["iid"]),
            body=note,
        )
    db.add(
        Artifact(
            run_id=run.id,
            kind="log",
            name="merge-request.json",
            content=str(mr),
        )
    )
    emit_event(
        db,
        run_id=run.id,
        kind="scm",
        message=f"GitLab MR created: {run.mr_url}",
        payload={"provider": "gitlab"},
    )
    db.commit()


def _fail(
    db: Session, run: WorkflowRun, error: str, stage_name: str = "engine"
) -> WorkflowRun:
    run.status = RunStatus.failed
    run.finished_at = _now()
    db.add(
        StageExecution(
            run_id=run.id,
            order_index=0,
            name=stage_name,
            agent_role="System",
            status=StageStatus.failed,
            error=error,
            finished_at=_now(),
        )
    )
    db.commit()
    db.refresh(run)
    return run


def _record_skipped(
    db: Session, run: WorkflowRun, index: int, name: str, role: str
) -> None:
    existing = next((s for s in run.stages if s.order_index == index), None)
    if existing:
        existing.status = StageStatus.skipped
    else:
        db.add(
            StageExecution(
                run_id=run.id,
                order_index=index,
                name=name,
                agent_role=role,
                status=StageStatus.skipped,
            )
        )
    db.commit()


def _capture_artifacts(db: Session, run: WorkflowRun, stage_name: str, output: dict) -> None:
    if stage_name == "report" and output.get("report_markdown"):
        db.add(
            Artifact(
                run_id=run.id,
                kind="report",
                name="final-report.md",
                content=output["report_markdown"],
            )
        )
    if stage_name == "develop" and output.get("diff"):
        db.add(
            Artifact(run_id=run.id, kind="patch", name="change.patch", content=output["diff"])
        )
    if stage_name == "sandbox_qa":
        # Persist Playwright product-E2E artifact paths (screenshot/video/trace).
        for result in output.get("results") or []:
            for path in result.get("artifacts") or []:
                name = Path(str(path)).name
                db.add(
                    Artifact(
                        run_id=run.id,
                        kind="playwright",
                        name=name,
                        content=str(path),
                    )
                )
        if output.get("artifact_dir"):
            artifact_dir = Path(str(output["artifact_dir"]))
            db.add(
                Artifact(
                    run_id=run.id,
                    kind="playwright",
                    name="artifact-dir",
                    content=str(artifact_dir),
                )
            )
            for log_name in ("server.log", "worker.log", "status.txt"):
                log_path = artifact_dir / log_name
                if log_path.exists():
                    db.add(
                        Artifact(
                            run_id=run.id,
                            kind="playwright",
                            name=log_name,
                            content=str(log_path),
                        )
                    )
            if output.get("logs"):
                db.add(
                    Artifact(
                        run_id=run.id,
                        kind="playwright",
                        name="sandbox-qa.log",
                        content=str(output["logs"])[:20_000],
                    )
                )
