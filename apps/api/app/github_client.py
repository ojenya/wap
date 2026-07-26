"""GitHub REST + OAuth helpers (browse repos, draft PRs)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urlencode

import httpx

from app.config import get_settings

GITHUB_API = "https://api.github.com"
GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
DEFAULT_SCOPES = "repo read:user"


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


def oauth_configured() -> bool:
    settings = get_settings()
    return bool(settings.github_oauth_client_id and settings.github_oauth_client_secret)


def oauth_authorize_url(state: str = "wap") -> str | None:
    settings = get_settings()
    if not settings.github_oauth_client_id:
        return None
    params = urlencode(
        {
            "client_id": settings.github_oauth_client_id,
            "redirect_uri": settings.github_oauth_redirect_uri,
            "scope": DEFAULT_SCOPES,
            "state": state,
            "allow_signup": "false",
        }
    )
    return f"{GITHUB_AUTHORIZE}?{params}"


def oauth_exchange_code(code: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret:
        raise GitHubError("GitHub OAuth is not configured")
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            GITHUB_TOKEN,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "code": code,
                "redirect_uri": settings.github_oauth_redirect_uri,
            },
        )
    if resp.status_code >= 400:
        raise GitHubError(f"OAuth token exchange failed: {resp.status_code} {resp.text}")
    payload = resp.json()
    if payload.get("error"):
        raise GitHubError(
            f"OAuth error: {payload.get('error_description') or payload.get('error')}"
        )
    if not payload.get("access_token"):
        raise GitHubError("OAuth response missing access_token")
    return payload


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "wap-change-factory",
    }


def fetch_current_user(token: str) -> dict[str, Any]:
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{GITHUB_API}/user", headers=_headers(token))
    if resp.status_code >= 400:
        raise GitHubError(f"GitHub user failed: {resp.status_code} {resp.text}")
    return resp.json()


def list_user_repos(token: str, search: str = "", per_page: int = 30) -> list[dict[str, Any]]:
    """List repositories visible to the authenticated user."""
    with httpx.Client(timeout=30) as client:
        resp = client.get(
            f"{GITHUB_API}/user/repos",
            headers=_headers(token),
            params={
                "per_page": per_page,
                "sort": "updated",
                "affiliation": "owner,collaborator,organization_member",
            },
        )
    if resp.status_code >= 400:
        raise GitHubError(f"GitHub repos failed: {resp.status_code} {resp.text}")
    repos = resp.json()
    if not isinstance(repos, list):
        return []
    if search:
        q = search.lower()
        repos = [
            r
            for r in repos
            if q in str(r.get("full_name", "")).lower() or q in str(r.get("name", "")).lower()
        ]
    return repos


def _request(
    method: str,
    path: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with httpx.Client(timeout=30) as client:
        resp = client.request(
            method,
            f"{GITHUB_API}{path}",
            headers=_headers(token),
            json=body,
        )
    if resp.status_code >= 400:
        raise GitHubError(f"GitHub API {resp.status_code}: {resp.text}")
    return resp.json() if resp.content else {}


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
