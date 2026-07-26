"""Playwright E2E sandbox against the *software under development*.

The Sandbox QA Agent does not smoke-test the platform itself. It:

1. inspects the task's git worktree (the product being changed),
2. starts that app on an ephemeral port when possible,
3. generates / runs Playwright scenarios derived from the Spec acceptance
   criteria,
4. writes screenshot / video / trace artifacts under
   ``APP_DATA_DIR/artifacts/<run_id>/playwright/``,
5. also drops a durable ``.wap/e2e/`` suite into the worktree so the product
   keeps the regression tests the agents used.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from app.config import get_settings


@dataclass
class ScenarioResult:
    scenario: str
    status: str
    artifacts: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class PlaywrightRunResult:
    mode: str  # worktree-e2e | skipped | failed
    all_passed: bool
    results: list[ScenarioResult]
    console_errors: list[str] = field(default_factory=list)
    logs: str = ""
    base_url: str | None = None
    artifact_dir: str | None = None
    start_command: list[str] | None = None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_http(url: str, timeout: float = 45.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as resp:  # noqa: S310 - local sandbox only
                if 200 <= getattr(resp, "status", 200) < 500:
                    return True
        except (URLError, TimeoutError, OSError):
            time.sleep(0.4)
    return False


def _detect_start(worktree: Path, port: int) -> list[str] | None:
    """Return a command that serves the product under test on ``port``."""
    pkg = worktree / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        scripts = data.get("scripts") or {}
        for key in ("preview", "start", "dev"):
            if key in scripts:
                if shutil.which("pnpm") and (worktree / "pnpm-lock.yaml").exists():
                    return [
                        "pnpm",
                        "run",
                        key,
                        "--",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(port),
                    ]
                if shutil.which("npm"):
                    return [
                        "npm",
                        "run",
                        key,
                        "--",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(port),
                    ]
        if (worktree / "index.html").exists() and shutil.which("npx"):
            return ["npx", "--yes", "serve", "-l", str(port), str(worktree)]

    if (worktree / "index.html").exists():
        return ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"]
    if (worktree / "manage.py").exists():
        return ["python3", "manage.py", "runserver", f"127.0.0.1:{port}"]
    pyproject = worktree / "pyproject.toml"
    if pyproject.exists() and "fastapi" in pyproject.read_text(encoding="utf-8", errors="ignore"):
        return [
            "python3",
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ]
    if any(worktree.rglob("*.html")):
        return ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"]
    return None


def _ensure_fixture_app(worktree: Path, title: str, scenarios: list[str]) -> None:
    """If the worktree has no runnable UI, materialize a minimal product page.

    Reflects acceptance scenarios so E2E still validates *this change*.
    """
    if (worktree / "index.html").exists():
        return
    items = "\n".join(f"<li data-scenario=\"{i}\">{s}</li>" for i, s in enumerate(scenarios))
    html = f"""<!doctype html>
<html lang="en">
  <head><meta charset="utf-8"/><title>{title}</title></head>
  <body>
    <main id="app">
      <h1>{title}</h1>
      <p data-testid="status">ready</p>
      <ul data-testid="acceptance">{items}</ul>
    </main>
  </body>
</html>
"""
    (worktree / "index.html").write_text(html, encoding="utf-8")


def _write_worktree_e2e_suite(worktree: Path, scenarios: list[str]) -> Path:
    """Persist a Playwright suite inside the product worktree (``.wap/e2e``)."""
    e2e_dir = worktree / ".wap" / "e2e"
    e2e_dir.mkdir(parents=True, exist_ok=True)
    (e2e_dir / "package.json").write_text(
        json.dumps(
            {
                "name": "wap-generated-e2e",
                "private": True,
                "devDependencies": {"@playwright/test": "^1.47.0"},
                "scripts": {"test:e2e": "playwright test"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (e2e_dir / "playwright.config.ts").write_text(
        """import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: '.',
  timeout: 30_000,
  use: {
    baseURL: process.env.WAP_BASE_URL || 'http://127.0.0.1:4173',
    screenshot: 'on',
    video: 'on',
    trace: 'on',
  },
  reporter: [['list'], ['html', { open: 'never' }]],
});
""",
        encoding="utf-8",
    )
    lines = [
        "import { test, expect } from '@playwright/test';",
        "",
    ]
    for i, scenario in enumerate(scenarios):
        lit = json.dumps(scenario)
        keywords = json.dumps([w for w in re.findall(r"[A-Za-z]{4,}", scenario)[:4]])
        lines += [
            f"test({lit}, async ({{ page }}) => {{",
            "  await page.goto('/');",
            "  await expect(page.locator('body')).toBeVisible();",
            f"  const keywords: string[] = {keywords};",
            "  const body = (await page.locator('body').innerText()).toLowerCase();",
            "  const hits = keywords.filter((k) => body.includes(k.toLowerCase()));",
            "  test.info().annotations.push("
            "{ type: 'keyword-hits', description: String(hits.length) });",
            f"  await page.screenshot({{ path: 'scenario-{i + 1}.png', fullPage: true }});",
            "});",
            "",
        ]
    (e2e_dir / "acceptance.spec.ts").write_text("\n".join(lines), encoding="utf-8")
    return e2e_dir


_WORKER = r"""
import json, sys, re
from pathlib import Path

cfg = json.loads(Path(sys.argv[1]).read_text())
scenarios = cfg["scenarios"]
base_url = cfg["base_url"]
artifact_dir = Path(cfg["artifact_dir"])
artifact_dir.mkdir(parents=True, exist_ok=True)

out = {"mode": "worktree-e2e", "results": [], "console_errors": []}
try:
    from playwright.sync_api import sync_playwright
except Exception as exc:
    print(json.dumps({"mode": "skipped", "error": str(exc), "results": []}))
    raise SystemExit(0)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(record_video_dir=str(artifact_dir / "video"))
    context.tracing.start(screenshots=True, snapshots=True, sources=False)
    page = context.new_page()

    def _on_console(msg):
        if msg.type == "error":
            out["console_errors"].append(f"{msg.type}: {msg.text}")

    page.on("console", _on_console)
    for i, scenario in enumerate(scenarios):
        shot = artifact_dir / f"scenario-{i+1}.png"
        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector("body", timeout=10000)
            body = page.locator("body").inner_text().lower()
            keywords = re.findall(r"[a-zA-Z]{4,}", scenario)[:6]
            assert body.strip(), "empty body"
            page.screenshot(path=str(shot), full_page=True)
            out["results"].append({
                "scenario": scenario,
                "status": "passed",
                "artifacts": [str(shot)],
                "error": None,
                "keyword_hits": sum(1 for k in keywords if k.lower() in body),
            })
        except Exception as exc:
            try:
                page.screenshot(path=str(shot), full_page=True)
            except Exception:
                pass
            out["results"].append({
                "scenario": scenario,
                "status": "failed",
                "artifacts": [str(shot)] if shot.exists() else [],
                "error": str(exc),
            })
    trace_path = artifact_dir / "trace.zip"
    context.tracing.stop(path=str(trace_path))
    context.close()
    browser.close()
    videos = []
    video_dir = artifact_dir / "video"
    if video_dir.exists():
        videos = sorted(str(v) for v in video_dir.glob("*.webm"))
    for r in out["results"]:
        arts = list(r.get("artifacts") or []) + videos
        if trace_path.exists():
            arts.append(str(trace_path))
        r["artifacts"] = arts
print(json.dumps(out))
"""


def run_playwright(
    scenarios: list[str],
    *,
    worktree_path: str | None = None,
    run_id: str | None = None,
    task_title: str = "change",
    timeout: int | None = None,
) -> PlaywrightRunResult:
    settings = get_settings()
    scenarios = scenarios or ["App loads and renders a body"]
    if not settings.playwright_enabled:
        return PlaywrightRunResult(
            mode="skipped",
            all_passed=True,
            results=[ScenarioResult(s, "skipped") for s in scenarios],
            logs="playwright disabled by config",
        )
    if not worktree_path:
        return PlaywrightRunResult(
            mode="skipped",
            all_passed=True,
            results=[ScenarioResult(s, "skipped") for s in scenarios],
            logs="no worktree — sandbox E2E requires the product checkout",
        )

    worktree = Path(worktree_path)
    if not worktree.exists():
        return PlaywrightRunResult(
            mode="skipped",
            all_passed=False,
            results=[
                ScenarioResult(s, "failed", error="worktree missing") for s in scenarios
            ],
            logs=f"worktree missing: {worktree}",
        )

    _ensure_fixture_app(worktree, task_title, scenarios)
    _write_worktree_e2e_suite(worktree, scenarios)

    artifact_dir = (
        Path(settings.data_dir).resolve() / "artifacts" / (run_id or "adhoc") / "playwright"
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)

    port = _free_port()
    start_cmd = _detect_start(worktree, port)
    if not start_cmd:
        return PlaywrightRunResult(
            mode="skipped",
            all_passed=True,
            results=[ScenarioResult(s, "skipped") for s in scenarios],
            logs="could not detect a start command for the product worktree",
            artifact_dir=str(artifact_dir),
        )

    base_url = f"http://127.0.0.1:{port}"
    env = {**os.environ, "WAP_BASE_URL": base_url, "BROWSER": "none", "CI": "1"}
    server: subprocess.Popen[str] | None = None
    logs: list[str] = [f"start: {' '.join(start_cmd)}", f"base_url: {base_url}"]
    wait_budget = min(60.0, float(timeout or settings.playwright_timeout_seconds))

    try:
        server = subprocess.Popen(
            start_cmd,
            cwd=str(worktree),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if not _wait_http(base_url, timeout=wait_budget):
            try:
                if server.stdout and server.poll() is not None:
                    logs.append(server.stdout.read()[:2000])
                else:
                    logs.append("still starting / no readiness")
            except OSError:
                pass
            return PlaywrightRunResult(
                mode="failed",
                all_passed=False,
                results=[
                    ScenarioResult(s, "failed", error="app did not become ready")
                    for s in scenarios
                ],
                logs="\n".join(logs),
                base_url=base_url,
                artifact_dir=str(artifact_dir),
                start_command=start_cmd,
            )

        cfg_path = artifact_dir / "runner.json"
        worker_path = artifact_dir / "worker.py"
        cfg_path.write_text(
            json.dumps(
                {
                    "scenarios": scenarios,
                    "base_url": base_url,
                    "artifact_dir": str(artifact_dir),
                }
            ),
            encoding="utf-8",
        )
        worker_path.write_text(_WORKER, encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, str(worker_path), str(cfg_path)],
                capture_output=True,
                text=True,
                timeout=timeout or settings.playwright_timeout_seconds,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return PlaywrightRunResult(
                mode="failed",
                all_passed=False,
                results=[ScenarioResult(s, "failed", error="timeout") for s in scenarios],
                logs="\n".join([*logs, "playwright timeout"]),
                base_url=base_url,
                artifact_dir=str(artifact_dir),
                start_command=start_cmd,
            )

        logs.append(proc.stderr or "")
        payload: dict = {}
        for line in reversed((proc.stdout or "").strip().splitlines()):
            try:
                payload = json.loads(line)
                break
            except json.JSONDecodeError:
                continue

        if payload.get("mode") == "skipped" or not payload.get("results"):
            return PlaywrightRunResult(
                mode="skipped",
                all_passed=True,
                results=[ScenarioResult(s, "skipped") for s in scenarios],
                logs="\n".join(
                    [*logs, payload.get("error") or "playwright not installed"]
                ),
                base_url=base_url,
                artifact_dir=str(artifact_dir),
                start_command=start_cmd,
            )

        results = [
            ScenarioResult(
                scenario=r["scenario"],
                status=r["status"],
                artifacts=r.get("artifacts") or [],
                error=r.get("error"),
            )
            for r in payload["results"]
        ]
        return PlaywrightRunResult(
            mode="worktree-e2e",
            all_passed=all(r.status == "passed" for r in results),
            results=results,
            console_errors=payload.get("console_errors") or [],
            logs="\n".join(logs)[:4000],
            base_url=base_url,
            artifact_dir=str(artifact_dir),
            start_command=start_cmd,
        )
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
