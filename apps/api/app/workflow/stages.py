"""Deterministic stub agents for each lifecycle stage.

These are intentionally rule-based (no external LLM calls) so the full workflow
runs reproducibly in any environment. Each stage produces structured, cited
output that mirrors what a real LLM/RAG/opencode-backed agent would return, and
exposes clear seams (``# EXTENSION POINT``) where a production agent plugs in.
"""

from __future__ import annotations

from pathlib import Path

from app.git_workspace import GitWorkspaceManager
from app.workflow.base import Stage
from app.workflow.contracts import Evidence, StageResult, WorkflowContext
from app.workflow.opencode_runner import OpencodeRequest, get_runner

# Keywords that mark a change as security/regulatory sensitive -> higher risk.
HIGH_RISK_KEYWORDS = (
    "auth",
    "password",
    "secret",
    "token",
    "payment",
    "billing",
    "migration",
    "database schema",
    "production",
    "encryption",
)


def _keywords(text: str) -> list[str]:
    stop = {"the", "and", "for", "with", "that", "this", "fix", "add", "when"}
    words = [w.strip(".,:;()[]").lower() for w in text.split()]
    return sorted({w for w in words if len(w) > 3 and w not in stop})


def _tokens(*parts: object) -> int:
    # Deterministic mock cost proportional to the text volume the agent handled.
    return sum(len(str(p)) for p in parts) // 4 + 25


class IntakeStage(Stage):
    name = "intake"
    agent_role = "Intake Agent"

    def run(self, context: WorkflowContext) -> StageResult:
        task = context.task
        haystack = f"{task.title} {task.description}".lower()
        risk = "high" if any(k in haystack for k in HIGH_RISK_KEYWORDS) else "medium"
        if len(task.description) < 20 and risk != "high":
            risk = "low"
        normalized = {
            "goal": task.title.strip(),
            "repo_url": task.repo_url,
            "base_branch": task.base_branch,
            "task_type": task.task_type,
            "risk_level": risk,
            "keywords": _keywords(haystack),
            "required_checks": ["lint", "typecheck", "unit_tests"]
            + (["security_scan"] if risk == "high" else []),
        }
        return StageResult(
            output=normalized,
            evidence=[Evidence(source="task", reference=task.id, reason="user request")],
            tokens=_tokens(haystack),
        )


class RepositoryContextStage(Stage):
    name = "repository_context"
    agent_role = "Repository Intelligence (RAG)"

    def run(self, context: WorkflowContext) -> StageResult:
        # Prefer real files from the per-run worktree when a repository is
        # connected. Full hybrid RAG (embeddings + BM25 + symbol graph) plugs
        # in here later; for now we do keyword ranking over tracked paths.
        intake = context.get("intake")
        keywords = intake.get("keywords", [])
        source = "synthetic"
        if context.worktree_path:
            files = GitWorkspaceManager().list_source_files(Path(context.worktree_path))
            if files:
                scored = sorted(
                    files,
                    key=lambda p: sum(1 for k in keywords if k in p.lower()),
                    reverse=True,
                )
                retrieved = scored[:6] or files[:6]
                source = "worktree"
            else:
                retrieved = [f"src/{kw}.ts" for kw in keywords[:3]] or ["src/index.ts"]
        else:
            retrieved = [f"src/{kw}.ts" for kw in keywords[:3]] or ["src/index.ts"]
            retrieved += [
                "tests/" + f.split("/")[-1].replace(".ts", ".test.ts") for f in retrieved
            ]
        evidence = [
            Evidence(source=source, reference=path, reason="path/keyword match")
            for path in retrieved
        ]
        return StageResult(
            output={
                "retrieval_strategy": "worktree keyword rank" if source == "worktree"
                else "synthetic (no repository attached)",
                "retrieved_files": retrieved,
                "commit_pinned": bool(context.head_sha),
                "head_sha": context.head_sha or None,
                "worktree_path": context.worktree_path or None,
            },
            evidence=evidence,
            tokens=_tokens(retrieved),
        )


class AuditStage(Stage):
    name = "audit"
    agent_role = "Audit Agent"

    def run(self, context: WorkflowContext) -> StageResult:
        intake = context.get("intake")
        risk = intake.get("risk_level", "medium")
        findings = [
            "Architecture: change is localized to retrieved modules.",
            "Dependencies: no new third-party packages required by scope.",
        ]
        if risk == "high":
            findings.append(
                "Security-sensitive area detected: human-in-the-loop gate required before merge."
            )
        return StageResult(
            output={
                "findings": findings,
                "requires_human_gate": risk == "high",
                "policy_violations": [],
            },
            evidence=[Evidence(source="policy", reference="audit-policy-v1")],
            tokens=_tokens(findings),
        )


class AnalysisStage(Stage):
    name = "analysis"
    agent_role = "Analysis Agent"

    def run(self, context: WorkflowContext) -> StageResult:
        ctx = context.get("repository_context")
        files = ctx.get("retrieved_files", [])
        affected = [f for f in files if not f.startswith("tests/")]
        tests = [f for f in files if f.startswith("tests/")]
        scenarios = [
            f"User can exercise '{context.task.title}' happy path",
            "Edge case: invalid input is rejected with a clear error",
        ]
        return StageResult(
            output={
                "affected_files": affected,
                "tests_to_run": tests,
                "playwright_scenarios": scenarios,
                "regression_risk": "medium" if len(affected) > 2 else "low",
            },
            evidence=[Evidence(source="rag", reference=f) for f in affected],
            tokens=_tokens(files, scenarios),
        )


class SpecStage(Stage):
    name = "spec"
    agent_role = "Spec Agent"

    def run(self, context: WorkflowContext) -> StageResult:
        task = context.task
        scenarios = context.get("analysis").get("playwright_scenarios", [])
        acceptance = [
            {"id": f"AC-{i + 1}", "criterion": s, "verification": "playwright"}
            for i, s in enumerate(scenarios)
        ]
        acceptance.append(
            {"id": f"AC-{len(acceptance) + 1}", "criterion": "All static checks pass",
             "verification": "static"}
        )
        return StageResult(
            output={
                "expected_behavior": task.description or task.title,
                "acceptance_criteria": acceptance,
                "out_of_scope": ["Unrelated refactors", "Dependency upgrades"],
            },
            evidence=[Evidence(source="analysis", reference="impact-map")],
            tokens=_tokens(acceptance),
        )


class ApprovalGateStage(Stage):
    name = "approval_gate"
    agent_role = "Policy Gate"

    def run(self, context: WorkflowContext) -> StageResult:
        requires_gate = context.get("audit").get("requires_human_gate", False)
        # EXTENSION POINT: block here until a human approves high-risk changes.
        # MVP auto-approves but records the decision for the audit trail.
        return StageResult(
            output={
                "gate_required": requires_gate,
                "decision": "auto-approved (MVP)" if requires_gate else "not required",
                "approved": True,
            },
            evidence=[Evidence(source="policy", reference="approval-gate-v1")],
            tokens=25,
        )


class DevelopStage(Stage):
    name = "develop"
    agent_role = "Implementation Agent (opencode runner)"

    def run(self, context: WorkflowContext) -> StageResult:
        # Audit-oriented tasks skip mutating the worktree.
        if context.task.task_type == "audit":
            return StageResult(
                output={
                    "branch": None,
                    "changed_files": [],
                    "diff": "",
                    "commands_executed": [],
                    "iterations": 0,
                    "skipped": True,
                    "reason": "audit tasks are read-only; develop stage skipped",
                    "worktree_path": context.worktree_path or None,
                },
                evidence=[Evidence(source="policy", reference="audit-readonly")],
                tokens=10,
            )

        affected = context.get("analysis").get("affected_files", ["src/index.ts"])
        slug = context.task.title.strip().replace(" ", "_").lower()[:40] or "change"
        workdir = context.worktree_path or None

        runner = get_runner()
        req = OpencodeRequest(
            task_title=context.task.title,
            task_description=context.task.description,
            acceptance_criteria=context.get("spec").get("acceptance_criteria", []),
            allowed_files=affected,
            base_branch=context.task.base_branch,
            workdir=workdir,
        )
        result = runner.run(req)

        if result.mode == "opencode":
            diff = result.diff
            changed = result.changed_files or affected
            commands = result.commands_executed
            develop_mode = "opencode"
        elif workdir:
            # Real worktree, no opencode key: apply a deterministic stub *inside*
            # the worktree so the artifact is a genuine git diff.
            target = affected[0]
            stub = (
                f"// Implements: {context.task.title}\n"
                f"export function {slug}() {{\n"
                f"  // worktree stub (opencode runner not configured)\n"
                f"  return true;\n"
                f"}}\n"
            )
            diff = GitWorkspaceManager().write_stub_change(Path(workdir), target, stub)
            changed = [target]
            commands = ["git worktree add", "stub patch applied in worktree"]
            develop_mode = "worktree-stub"
        else:
            diff = self._stub_patch(affected[0], context.task.title, slug)
            changed = affected
            commands = ["synthetic stub (no repository / worktree)"]
            develop_mode = "synthetic-stub"

        return StageResult(
            output={
                "branch": f"agent/{slug}",
                "changed_files": changed,
                "diff": diff,
                "commands_executed": commands,
                "iterations": 1,
                "develop_mode": develop_mode,
                "worktree_path": workdir,
                "runner": {
                    "mode": result.mode,
                    "available": result.available,
                    "plan": result.plan,
                    "model": result.model,
                    "base_url": result.base_url,
                },
            },
            evidence=[Evidence(source="opencode", reference=f"session/{slug}")],
            tokens=_tokens(diff),
        )

    @staticmethod
    def _stub_patch(target: str, title: str, slug: str) -> str:
        return (
            f"--- a/{target}\n+++ b/{target}\n"
            "@@\n"
            f"+// Implements: {title}\n"
            f"+export function {slug}() {{\n"
            "+  // deterministic MVP stub (no worktree)\n"
            "+  return true;\n"
            "+}\n"
        )


class StaticChecksStage(Stage):
    name = "static_checks"
    agent_role = "Static Test Agent"

    def run(self, context: WorkflowContext) -> StageResult:
        checks = context.get("intake").get("required_checks", ["lint"])
        cmd_map = {
            "lint": "eslint .",
            "typecheck": "tsc --noEmit",
            "unit_tests": "vitest run",
            "security_scan": "gitleaks detect",
        }
        results = [
            {"check": c, "command": cmd_map.get(c, c), "exit_code": 0, "status": "passed"}
            for c in checks
        ]
        return StageResult(
            output={"results": results, "all_passed": True},
            evidence=[Evidence(source="ci", reference=r["command"]) for r in results],
            tokens=_tokens(results),
        )


class SandboxQAStage(Stage):
    name = "sandbox_qa"
    agent_role = "Sandbox QA Agent"

    def run(self, context: WorkflowContext) -> StageResult:
        # EXTENSION POINT: run Playwright in a disposable Docker sandbox and
        # collect trace/video/screenshots/HAR.
        scenarios = context.get("analysis").get("playwright_scenarios", [])
        results = [
            {"scenario": s, "status": "passed", "artifacts": [f"trace-{i}.zip"]}
            for i, s in enumerate(scenarios)
        ]
        return StageResult(
            output={"results": results, "all_passed": True, "console_errors": []},
            evidence=[Evidence(source="playwright", reference=r["artifacts"][0]) for r in results],
            tokens=_tokens(results),
        )


class ReviewStage(Stage):
    name = "review"
    agent_role = "Review Agent"

    def run(self, context: WorkflowContext) -> StageResult:
        criteria = context.get("spec").get("acceptance_criteria", [])
        static_ok = context.get("static_checks").get("all_passed", False)
        sandbox_ok = context.get("sandbox_qa").get("all_passed", False)
        compliance = [
            {"id": c["id"], "criterion": c["criterion"],
             "result": "pass" if (static_ok and sandbox_ok) else "fail"}
            for c in criteria
        ]
        approved = static_ok and sandbox_ok
        return StageResult(
            output={
                "spec_compliance": compliance,
                "regression_notes": context.get("analysis").get("regression_risk", "low"),
                "approved": approved,
            },
            evidence=[Evidence(source="review", reference="diff-review")],
            tokens=_tokens(compliance),
        )


class ReportStage(Stage):
    name = "report"
    agent_role = "Report Agent"

    def run(self, context: WorkflowContext) -> StageResult:
        task = context.task
        review = context.get("review")
        develop = context.get("develop")
        compliance = review.get("spec_compliance", [])
        checks = context.get("static_checks").get("results", [])
        lines = [
            f"# Report: {task.title}",
            "",
            "## Executive summary",
            f"- Status: {'APPROVED' if review.get('approved') else 'CHANGES REQUESTED'}",
            f"- Risk level: {context.get('intake').get('risk_level')}",
            f"- Branch: {develop.get('branch', 'n/a')}",
            "",
            "## Scope",
            f"- Repo: {task.repo_url or 'n/a'} @ {task.base_branch}",
            f"- Changed files: {', '.join(develop.get('changed_files', [])) or 'none'}",
            "",
            "## Spec compliance",
        ]
        lines += [f"- {c['id']}: {c['result']} - {c['criterion']}" for c in compliance]
        lines += ["", "## Static checks"]
        lines += [f"- {c['command']} -> exit {c['exit_code']} ({c['status']})" for c in checks]
        report_md = "\n".join(lines)
        return StageResult(
            output={"report_markdown": report_md, "approved": review.get("approved", False)},
            evidence=[Evidence(source="report", reference="final-report")],
            tokens=_tokens(report_md),
        )


class LearningStage(Stage):
    name = "learning"
    agent_role = "Learning Agent"

    def run(self, context: WorkflowContext) -> StageResult:
        # EXTENSION POINT: persist validated case memory / eval dataset entries,
        # gated on successful CI + human approval to avoid memory rot.
        approved = context.get("review").get("approved", False)
        lessons = [
            f"Task type '{context.task.task_type}' completed with "
            f"{len(context.get('develop').get('changed_files', []))} file(s) changed.",
        ]
        return StageResult(
            output={
                "validated": approved,
                "lessons": lessons,
                "stored_in": "operational_memory" if approved else "skipped",
            },
            evidence=[Evidence(source="learning", reference="case-memory")],
            tokens=_tokens(lessons),
        )
