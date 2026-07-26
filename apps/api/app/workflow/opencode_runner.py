"""opencode runner adapter (Implementation Agent).

This is the concrete seam where the platform delegates code changes to the
terminal-native `opencode` agent, oriented to the **opencode Zen** (pay-per-use)
or **opencode Go** (subscription) plans. Both share the ``OPENCODE_API_KEY``
credential and differ only by base URL (see ``app.config``).

The runner:
  * builds an isolated ``opencode.json`` (provider base URL, model, an allow/ask
    permission profile for the ``build`` agent),
  * invokes ``opencode run --format json`` headlessly in a worktree, and
  * collects the resulting git diff, changed files and session logs.

When the ``opencode`` CLI or an API key is not available, ``run`` returns an
``unavailable`` result so callers (``DevelopStage``) can fall back to the
deterministic stub and keep the workflow runnable without credentials.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings, get_settings


@dataclass
class OpencodeRequest:
    task_title: str
    task_description: str = ""
    acceptance_criteria: list[dict] = field(default_factory=list)
    allowed_files: list[str] = field(default_factory=list)
    base_branch: str = "main"
    # Absolute path to an isolated worktree/checkout. When None the runner is
    # only used for availability/config inspection (no real coding session).
    workdir: str | None = None


@dataclass
class OpencodeResult:
    mode: str  # "opencode" | "unavailable" | "error"
    available: bool
    plan: str
    model: str
    base_url: str
    diff: str = ""
    changed_files: list[str] = field(default_factory=list)
    commands_executed: list[str] = field(default_factory=list)
    logs: str = ""
    error: str | None = None


class OpencodeRunner:
    """Thin adapter that hides opencode CLI/config details from the orchestrator."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def is_available(self) -> bool:
        """True only when opencode is enabled, has a key, and the CLI is installed."""
        return (
            self.settings.opencode_enabled
            and bool(self.settings.opencode_api_key)
            and shutil.which("opencode") is not None
        )

    def build_config(self) -> dict:
        """Build the ``opencode.json`` oriented to the configured Zen/Go plan."""
        model = self.settings.opencode_model
        return {
            "$schema": "https://opencode.ai/config.json",
            "model": model,
            "provider": {
                "opencode": {
                    "options": {"baseURL": self.settings.opencode_base_url},
                }
            },
            "agent": {
                "build": {
                    "mode": "primary",
                    "model": model,
                    # Least-privilege profile: edits allowed, shell gated, no network.
                    "permission": {"edit": "allow", "bash": "ask", "webfetch": "deny"},
                }
            },
        }

    def build_prompt(self, req: OpencodeRequest) -> str:
        lines = [
            f"Task: {req.task_title}",
            "",
            req.task_description or "",
            "",
            "Acceptance criteria:",
        ]
        lines += [f"- {c.get('id', '')}: {c.get('criterion', '')}" for c in req.acceptance_criteria]
        if req.allowed_files:
            lines += ["", "Only modify these files:", *[f"- {f}" for f in req.allowed_files]]
        lines += ["", "Make the minimal change that satisfies the criteria. Do not add scope."]
        return "\n".join(lines)

    def run(self, req: OpencodeRequest) -> OpencodeResult:
        base = OpencodeResult(
            mode="unavailable",
            available=self.is_available(),
            plan=self.settings.opencode_plan,
            model=self.settings.opencode_model,
            base_url=self.settings.opencode_base_url,
        )
        if not base.available or not req.workdir:
            return base

        workdir = Path(req.workdir)
        config_path = workdir / "opencode.json"
        config_path.write_text(json.dumps(self.build_config(), indent=2), encoding="utf-8")

        env = {
            **os.environ,
            "OPENCODE_API_KEY": self.settings.opencode_api_key,
            "OPENCODE_CONFIG": str(config_path),
            "OPENCODE_DISABLE_AUTOUPDATE": "1",
        }
        cmd = [
            "opencode", "run", "--format", "json",
            "-m", self.settings.opencode_model,
            "--agent", "build",
            self.build_prompt(req),
        ]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(workdir),
                env=env,
                capture_output=True,
                text=True,
                timeout=self.settings.opencode_timeout_seconds,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            base.mode = "error"
            base.error = str(exc)
            return base

        diff = self._git(workdir, ["diff"])
        changed = [f for f in self._git(workdir, ["diff", "--name-only"]).splitlines() if f]
        base.mode = "opencode" if proc.returncode == 0 else "error"
        base.diff = diff
        base.changed_files = changed
        base.commands_executed = [" ".join(cmd[:6])]
        base.logs = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            base.error = f"opencode exited with code {proc.returncode}"
        return base

    @staticmethod
    def _git(workdir: Path, args: list[str]) -> str:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=30,
            )
            return out.stdout
        except (subprocess.SubprocessError, OSError):
            return ""


def get_runner() -> OpencodeRunner:
    return OpencodeRunner(get_settings())
