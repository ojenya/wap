"""OAuth connection flow tests (GitLab / GitHub) without real providers."""

from __future__ import annotations

from app.models import OAuthProvider, RepoStatus
from app.oauth_service import (
    complete_oauth,
    connect_repository_from_oauth,
    list_remote_repos,
    providers_status,
    start_oauth,
)
from app.security import decrypt_secret


def test_providers_status_reflects_config(monkeypatch):
    monkeypatch.setenv("APP_GITLAB_OAUTH_CLIENT_ID", "gl-id")
    monkeypatch.setenv("APP_GITLAB_OAUTH_CLIENT_SECRET", "gl-secret")
    monkeypatch.setenv("APP_GITHUB_OAUTH_CLIENT_ID", "")
    monkeypatch.setenv("APP_GITHUB_OAUTH_CLIENT_SECRET", "")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        status = providers_status()
        assert status["gitlab"]["configured"] is True
        assert status["github"]["configured"] is False
    finally:
        get_settings.cache_clear()


def test_oauth_start_and_callback_gitlab(db_session, monkeypatch):
    monkeypatch.setenv("APP_GITLAB_OAUTH_CLIENT_ID", "gl-id")
    monkeypatch.setenv("APP_GITLAB_OAUTH_CLIENT_SECRET", "gl-secret")
    from app.config import get_settings

    get_settings.cache_clear()

    def fake_exchange(code: str):
        assert code == "auth-code"
        return {
            "access_token": "gl-access-token",
            "refresh_token": "gl-refresh",
            "scope": "api",
            "expires_in": 7200,
        }

    def fake_user(token: str):
        assert token == "gl-access-token"
        return {"id": 42, "username": "alice", "name": "Alice"}

    monkeypatch.setattr("app.oauth_service.gitlab_client.oauth_exchange_code", fake_exchange)
    monkeypatch.setattr("app.oauth_service.gitlab_client.fetch_current_user", fake_user)

    try:
        started = start_oauth(db_session, OAuthProvider.gitlab)
        assert "gitlab.com" in started["url"] or "oauth/authorize" in started["url"]
        assert started["state"]

        conn = complete_oauth(
            db_session,
            OAuthProvider.gitlab,
            code="auth-code",
            state=started["state"],
        )
        assert conn.account_login == "alice"
        assert decrypt_secret(conn.access_token_encrypted) == "gl-access-token"

        # state cannot be reused
        try:
            complete_oauth(
                db_session,
                OAuthProvider.gitlab,
                code="auth-code",
                state=started["state"],
            )
            raise AssertionError("expected reuse to fail")
        except Exception as exc:
            assert "state" in str(exc).lower() or "Invalid" in str(exc)
    finally:
        get_settings.cache_clear()


def test_oauth_github_list_and_connect(db_session, monkeypatch, tmp_path):
    monkeypatch.setenv("APP_GITHUB_OAUTH_CLIENT_ID", "gh-id")
    monkeypatch.setenv("APP_GITHUB_OAUTH_CLIENT_SECRET", "gh-secret")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    from app.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        "app.oauth_service.github_client.oauth_exchange_code",
        lambda code: {"access_token": "gh-token", "scope": "repo"},
    )
    monkeypatch.setattr(
        "app.oauth_service.github_client.fetch_current_user",
        lambda token: {"id": 7, "login": "bob", "name": "Bob"},
    )
    monkeypatch.setattr(
        "app.oauth_service.github_client.list_user_repos",
        lambda token, search="": [
            {
                "id": 99,
                "name": "widget",
                "full_name": "bob/widget",
                "clone_url": "https://github.com/bob/widget.git",
                "default_branch": "main",
            }
        ],
    )

    # Avoid real git clone in connect — stub mirror.
    class FakeMgr:
        def ensure_mirror(self, repo, db=None):
            p = tmp_path / "mirror"
            p.mkdir(exist_ok=True)
            return p

        def resolve_head(self, path, branch):
            return "abc123"

    monkeypatch.setattr("app.oauth_service.GitWorkspaceManager", FakeMgr)

    try:
        started = start_oauth(db_session, OAuthProvider.github)
        conn = complete_oauth(
            db_session,
            OAuthProvider.github,
            code="gh-code",
            state=started["state"],
        )
        repos = list_remote_repos(db_session, conn)
        assert repos[0]["full_name"] == "bob/widget"

        repo = connect_repository_from_oauth(
            db_session,
            conn,
            external_id="99",
            name="widget",
            clone_url="https://github.com/bob/widget.git",
            default_branch="main",
        )
        assert repo.status == RepoStatus.ready
        assert repo.head_sha == "abc123"
        assert decrypt_secret(repo.token_encrypted) == "gh-token"
    finally:
        get_settings.cache_clear()


def test_api_oauth_endpoints(client, monkeypatch):
    monkeypatch.setenv("APP_GITLAB_OAUTH_CLIENT_ID", "gl-id")
    monkeypatch.setenv("APP_GITLAB_OAUTH_CLIENT_SECRET", "gl-secret")
    from app.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        "app.oauth_service.gitlab_client.oauth_exchange_code",
        lambda code: {"access_token": "tok", "scope": "api"},
    )
    monkeypatch.setattr(
        "app.oauth_service.gitlab_client.fetch_current_user",
        lambda token: {"id": 1, "username": "ops", "name": "Ops"},
    )
    monkeypatch.setattr(
        "app.oauth_service.gitlab_client.list_projects",
        lambda token, search="": [],
    )

    try:
        providers = client.get("/api/oauth/providers")
        assert providers.status_code == 200
        assert providers.json()["gitlab"]["configured"] is True

        start = client.get("/api/oauth/gitlab/start")
        assert start.status_code == 200
        state = start.json()["state"]

        cb = client.post(
            "/api/oauth/gitlab/callback",
            json={"code": "x", "state": state},
        )
        assert cb.status_code == 200
        assert cb.json()["account_login"] == "ops"
        assert "access_token" not in cb.json()

        listed = client.get("/api/oauth/connections")
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        conn_id = listed.json()[0]["id"]

        repos = client.get(f"/api/oauth/connections/{conn_id}/repos")
        assert repos.status_code == 200
        assert repos.json() == []
    finally:
        get_settings.cache_clear()
