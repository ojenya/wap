"""GitHub client unit tests (no network)."""

from __future__ import annotations

from app.github_client import parse_github_repo


def test_parse_various_github_urls():
    assert parse_github_repo("https://github.com/acme/widget") == ("acme", "widget")
    assert parse_github_repo("https://github.com/acme/widget.git") == ("acme", "widget")
    assert parse_github_repo("git@github.com:acme/widget.git") == ("acme", "widget")
    assert parse_github_repo("https://gitlab.com/acme/widget") is None
