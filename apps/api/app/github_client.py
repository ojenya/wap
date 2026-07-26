"""Minimal GitHub REST client for draft PR creation (last-mile SCM)."""

from __future__ import annotations

import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

GITHUB_API = "https://api.github.com"


class GitHubError(RuntimeError):
    pass


def parse_github_repo(url: str) -> tuple[str, str] | None:
    """Return (owner, repo) from common GitHub URL shapes."""
    patterns = [
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+?)(?:\.git)?$",
        r"github\.com/(?P<owner>[^/]+)/(?P<repo>[^/.]+)",
    ]
    for pat in patterns:
        m = re.search(pat, url.strip())
        if m:
            return m.group("owner"), m.group("repo")
    return None


def _request(
    method: str,
    path: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import json

    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(
        f"{GITHUB_API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "wap-change-factory",
        },
    )
    try:
        with urlopen(req, timeout=30) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise GitHubError(f"GitHub API {exc.code}: {detail}") from exc
    except URLError as exc:
        raise GitHubError(str(exc)) from exc


def create_pull_request(
    token: str,
    owner: str,
    repo: str,
    *,
    title: str,
    head: str,
    base: str,
    body: str = "",
    draft: bool = True,
) -> dict[str, Any]:
    return _request(
        "POST",
        f"/repos/{quote(owner)}/{quote(repo)}/pulls",
        token,
        {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "draft": draft,
        },
    )


def post_pr_comment(
    token: str,
    owner: str,
    repo: str,
    pull_number: int,
    body: str,
) -> dict[str, Any]:
    return _request(
        "POST",
        f"/repos/{quote(owner)}/{quote(repo)}/issues/{pull_number}/comments",
        token,
        {"body": body},
    )
