"""Git mirror + worktree manager.

Every coding/audit run that is bound to a connected repository gets an
isolated git worktree under ``APP_DATA_DIR/worktrees/<run_id>``. The durable
clone lives in ``APP_DATA_DIR/mirrors/<repo_id>`` so subsequent runs only
``fetch`` instead of recloning.

This is the isolation layer the plan requires: opencode (and stub develop)
never touch a shared working tree.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse, urlunparse

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Repository
from app.security import decrypt_secret, reveal_repo_token


class GitWorkspaceError(RuntimeError):
    pass


@dataclass
class WorktreeInfo:
    path: Path
    branch: str
    head_sha: str
    mirror_path: Path


def detect_provider(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "gitlab" in host:
        return "gitlab"
    if "github" in host:
        return "github"
    return "git"


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> str:
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise GitWorkspaceError(str(exc)) from exc
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "git command failed").strip()
        raise GitWorkspaceError(err)
    return (proc.stdout or "").strip()


def authenticated_url(url: str, token: str) -> str:
    """Inject a token into an https git URL (GitLab oauth2 / GitHub x-access-token)."""
    if not token:
        return url
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return url
    host = (parsed.hostname or "").lower()
    user = "oauth2" if "gitlab" in host else "x-access-token" if "github" in host else "oauth2"
    netloc = f"{user}:{quote(token, safe='')}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))


def safe_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")[:60] or "change"


class GitWorkspaceManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = Path(self.settings.data_dir).resolve()
        self.mirrors = self.root / "mirrors"
        self.worktrees = self.root / "worktrees"
        self.mirrors.mkdir(parents=True, exist_ok=True)
        self.worktrees.mkdir(parents=True, exist_ok=True)
        # Tolerate host-mounted repos owned by a different uid (common in Docker).
        try:
            _run(["git", "config", "--global", "--add", "safe.directory", "*"])
        except GitWorkspaceError:
            pass

    def mirror_path(self, repo_id: str) -> Path:
        return self.mirrors / repo_id

    def ensure_mirror(self, repo: Repository, db: Session | None = None) -> Path:
        """Clone (or fetch) the durable mirror for ``repo``. Returns the path."""
        path = self.mirror_path(repo.id)
        if repo.token_encrypted and db is not None:
            token = reveal_repo_token(
                db,
                repository_id=repo.id,
                token_encrypted=repo.token_encrypted,
                purpose="git_mirror_sync",
            )
        else:
            token = decrypt_secret(repo.token_encrypted) if repo.token_encrypted else ""
        remote = authenticated_url(repo.url, token)
        if not (path / ".git").exists() and not (path / "HEAD").exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            # Full clone (not bare) so `git worktree add` is straightforward.
            _run(["git", "clone", "--no-checkout", remote, str(path)], timeout=300)
        else:
            # Refresh without leaking the token into logs of subsequent remotes:
            # temporarily set origin URL, fetch, then scrub credentials.
            _run(["git", "remote", "set-url", "origin", remote], cwd=path)
            _run(["git", "fetch", "--all", "--prune"], cwd=path, timeout=300)
        # Always scrub credentials from the stored remote URL.
        _run(["git", "remote", "set-url", "origin", repo.url], cwd=path)
        return path

    def create_worktree(
        self,
        repo: Repository,
        run_id: str,
        branch: str | None = None,
        db: Session | None = None,
    ) -> WorktreeInfo:
        """Create an isolated worktree for a workflow run."""
        mirror = self.ensure_mirror(repo, db=db)
        branch = branch or repo.default_branch
        target = self.worktrees / run_id
        if target.exists():
            # Idempotent: reuse an existing worktree directory for the same run.
            sha = _run(["git", "rev-parse", "HEAD"], cwd=target)
            return WorktreeInfo(path=target, branch=branch, head_sha=sha, mirror_path=mirror)

        # Prefer creating a local branch tracking origin/<branch>.
        local_branch = f"run/{safe_slug(run_id)}"
        try:
            _run(
                [
                    "git", "worktree", "add", "-b", local_branch,
                    str(target), f"origin/{branch}",
                ],
                cwd=mirror,
            )
        except GitWorkspaceError:
            # Fallback: branch name may already be local; try without -b.
            _run(
                ["git", "worktree", "add", str(target), f"origin/{branch}"],
                cwd=mirror,
            )
        sha = _run(["git", "rev-parse", "HEAD"], cwd=target)
        return WorktreeInfo(path=target, branch=branch, head_sha=sha, mirror_path=mirror)

    def resolve_head(self, mirror: Path, branch: str) -> str:
        try:
            return _run(["git", "rev-parse", f"origin/{branch}"], cwd=mirror)
        except GitWorkspaceError:
            return _run(["git", "rev-parse", "HEAD"], cwd=mirror)

    def list_source_files(self, worktree: Path, limit: int = 40) -> list[str]:
        """List tracked source-ish files from the worktree (for RAG stub context)."""
        try:
            out = _run(["git", "ls-files"], cwd=worktree)
        except GitWorkspaceError:
            return []
        files = []
        skip_prefixes = (".git/", "node_modules/", "dist/", "build/", ".venv/")
        for line in out.splitlines():
            if not line or line.startswith(skip_prefixes):
                continue
            if any(line.endswith(ext) for ext in (
                ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
                ".md", ".yml", ".yaml", ".toml", ".json",
            )):
                files.append(line)
            if len(files) >= limit:
                break
        return files

    def write_stub_change(self, worktree: Path, relative_path: str, content: str) -> str:
        """Apply a stub file change inside the worktree and return ``git diff``."""
        target = worktree / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        sep = "\n" if existing and not existing.endswith("\n") else ""
        target.write_text(existing + sep + content, encoding="utf-8")
        _run(["git", "add", "--", relative_path], cwd=worktree)
        # Prefer staged+unstaged unified diff for the artifact.
        try:
            return _run(["git", "diff", "--cached", "--", relative_path], cwd=worktree)
        except GitWorkspaceError:
            return _run(["git", "diff", "--", relative_path], cwd=worktree)
