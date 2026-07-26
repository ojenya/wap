"""Parallel subagent fan-out (explore / fix / test), Cursor multitask-inspired."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SubagentResult:
    role: str
    status: str
    findings: list[str] = field(default_factory=list)
    tokens: int = 0


def _explore(task_title: str, files: list[str]) -> SubagentResult:
    hits = [f for f in files if any(k in f.lower() for k in ("src", "app", "lib", "component"))]
    return SubagentResult(
        role="explore",
        status="completed",
        findings=[
            f"Mapped {len(files)} retrieved files for '{task_title}'",
            *(f"Hotspot: {h}" for h in hits[:5]),
        ],
        tokens=max(10, len(files) * 3),
    )


def _fix(task_title: str, files: list[str]) -> SubagentResult:
    targets = files[:3] or ["(no files — propose synthetic patch site)"]
    return SubagentResult(
        role="fix",
        status="completed",
        findings=[
            f"Proposed change sites for '{task_title}'",
            *(f"Edit candidate: {t}" for t in targets),
        ],
        tokens=40,
    )


def _test(task_title: str, files: list[str]) -> SubagentResult:
    tests = [f for f in files if "test" in f.lower()] or ["generated e2e scenarios"]
    return SubagentResult(
        role="test",
        status="completed",
        findings=[
            f"Test plan for '{task_title}'",
            *(f"Cover: {t}" for t in tests[:5]),
        ],
        tokens=30,
    )


_ROLE_FNS = {
    "explore": _explore,
    "fix": _fix,
    "test": _test,
}


def run_parallel_subagents(
    task_title: str,
    files: list[str],
    roles: list[str] | None = None,
    max_workers: int = 3,
) -> dict[str, Any]:
    """Fan-out subagents concurrently and merge findings."""
    selected = roles or ["explore", "fix", "test"]
    results: list[SubagentResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_ROLE_FNS[role], task_title, files): role
            for role in selected
            if role in _ROLE_FNS
        }
        for fut in as_completed(futures):
            results.append(fut.result())
    results.sort(key=lambda r: selected.index(r.role) if r.role in selected else 99)
    return {
        "parallel": True,
        "subagents": [
            {
                "role": r.role,
                "status": r.status,
                "findings": r.findings,
                "tokens": r.tokens,
            }
            for r in results
        ],
        "merged_findings": [f for r in results for f in r.findings],
        "tokens": sum(r.tokens for r in results),
    }
