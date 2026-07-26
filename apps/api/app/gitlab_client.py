"""GitLab API helpers: projects, branches, merge requests, OAuth URL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from app.config import get_settings


class GitLabError(RuntimeError):
    pass


@dataclass
class GitLabProject:
    id: int
    name: str
    path_with_namespace: str
    http_url_to_repo: str
    default_branch: str


def oauth_authorize_url(state: str = "wap") -> str | None:
    settings = get_settings()
    if not settings.gitlab_oauth_client_id:
        return None
    params = urlencode(
        {
            "client_id": settings.gitlab_oauth_client_id,
            "redirect_uri": settings.gitlab_oauth_redirect_uri,
            "response_type": "code",
            "scope": "api read_repository write_repository",
            "state": state,
        }
    )
    return f"{settings.gitlab_base_url.rstrip('/')}/oauth/authorize?{params}"


def oauth_exchange_code(code: str) -> str:
    settings = get_settings()
    if not settings.gitlab_oauth_client_id or not settings.gitlab_oauth_client_secret:
        raise GitLabError("GitLab OAuth is not configured")
    url = f"{settings.gitlab_base_url.rstrip('/')}/oauth/token"
    data = {
        "client_id": settings.gitlab_oauth_client_id,
        "client_secret": settings.gitlab_oauth_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.gitlab_oauth_redirect_uri,
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, data=data)
    if resp.status_code >= 400:
        raise GitLabError(f"OAuth token exchange failed: {resp.status_code} {resp.text}")
    token = resp.json().get("access_token")
    if not token:
        raise GitLabError("OAuth response missing access_token")
    return token


def _headers(token: str) -> dict[str, str]:
    return {"PRIVATE-TOKEN": token, "Authorization": f"Bearer {token}"}


def list_projects(token: str, search: str = "", per_page: int = 20) -> list[GitLabProject]:
    settings = get_settings()
    params: dict[str, Any] = {
        "membership": "true",
        "simple": "true",
        "per_page": per_page,
        "order_by": "last_activity_at",
    }
    if search:
        params["search"] = search
    url = f"{settings.gitlab_base_url.rstrip('/')}/api/v4/projects"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=_headers(token), params=params)
    if resp.status_code >= 400:
        raise GitLabError(f"list projects failed: {resp.status_code} {resp.text}")
    out: list[GitLabProject] = []
    for p in resp.json():
        out.append(
            GitLabProject(
                id=p["id"],
                name=p.get("name") or p.get("path_with_namespace"),
                path_with_namespace=p.get("path_with_namespace", ""),
                http_url_to_repo=p.get("http_url_to_repo") or p.get("web_url", ""),
                default_branch=p.get("default_branch") or "main",
            )
        )
    return out


def list_branches(token: str, project_id: int) -> list[str]:
    settings = get_settings()
    url = f"{settings.gitlab_base_url.rstrip('/')}/api/v4/projects/{project_id}/repository/branches"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=_headers(token), params={"per_page": 50})
    if resp.status_code >= 400:
        raise GitLabError(f"list branches failed: {resp.status_code} {resp.text}")
    return [b["name"] for b in resp.json()]


def create_merge_request(
    token: str,
    project_id: int,
    *,
    source_branch: str,
    target_branch: str,
    title: str,
    description: str,
) -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.gitlab_base_url.rstrip('/')}/api/v4/projects/{project_id}/merge_requests"
    payload = {
        "source_branch": source_branch,
        "target_branch": target_branch,
        "title": title,
        "description": description,
        "remove_source_branch": False,
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, headers=_headers(token), json=payload)
    if resp.status_code >= 400:
        raise GitLabError(f"create MR failed: {resp.status_code} {resp.text}")
    return resp.json()


def post_mr_note(token: str, project_id: int, mr_iid: int, body: str) -> None:
    settings = get_settings()
    url = (
        f"{settings.gitlab_base_url.rstrip('/')}/api/v4/projects/{project_id}"
        f"/merge_requests/{mr_iid}/notes"
    )
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, headers=_headers(token), json={"body": body})
    if resp.status_code >= 400:
        raise GitLabError(f"MR note failed: {resp.status_code} {resp.text}")


def push_branch(worktree: str, remote_url: str, branch: str) -> None:
    """Push the current HEAD of a worktree to remote as ``branch``."""
    import subprocess

    # Set a temporary remote with credentials already embedded by caller.
    subprocess.run(
        ["git", "remote", "remove", "publish"],
        cwd=worktree,
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ["git", "remote", "add", "publish", remote_url],
        cwd=worktree,
        capture_output=True,
        check=True,
    )
    # Commit any staged stub changes if present.
    subprocess.run(["git", "add", "-A"], cwd=worktree, capture_output=True, check=False)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=worktree, capture_output=True, text=True, check=False
    )
    if status.stdout.strip():
        subprocess.run(
            ["git", "-c", "user.email=agent@wap.local", "-c", "user.name=Change Factory",
             "commit", "-m", f"agent: {branch}"],
            cwd=worktree,
            capture_output=True,
            check=False,
        )
    proc = subprocess.run(
        ["git", "push", "-u", "publish", f"HEAD:refs/heads/{quote(branch, safe='/_-')}"],
        cwd=worktree,
        capture_output=True,
        text=True,
        check=False,
    )
    # Clean credentials from remote.
    subprocess.run(
        ["git", "remote", "remove", "publish"],
        cwd=worktree,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GitLabError(proc.stderr or proc.stdout or "git push failed")
