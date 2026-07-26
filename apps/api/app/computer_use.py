"""Computer-use / desktop verification seam (Cursor Desktop-inspired).

Headless Playwright covers automated E2E. This module records a desktop
verification session that operators (or a future VNC/computer-use agent) can
attach to — same product worktree, same base URL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class DesktopSession:
    status: str  # ready | skipped | failed
    base_url: str | None = None
    worktree_path: str | None = None
    instructions: list[str] = field(default_factory=list)
    takeover_supported: bool = True
    created_at: str = ""
    notes: str = ""


def prepare_desktop_session(
    *,
    worktree_path: str | None,
    base_url: str | None,
    scenarios: list[str] | None = None,
) -> DesktopSession:
    now = datetime.now(UTC).isoformat()
    if not worktree_path:
        return DesktopSession(
            status="skipped",
            created_at=now,
            notes="No product worktree — desktop verification unavailable",
        )
    if not base_url:
        return DesktopSession(
            status="skipped",
            worktree_path=worktree_path,
            created_at=now,
            notes="App URL unknown — run Playwright sandbox first",
        )
    steps = [
        f"Open desktop pane and navigate to {base_url}",
        "Verify the product under development renders",
        *(f"Manual check: {s}" for s in (scenarios or [])[:5]),
        "Confirm completion so the agent can continue",
    ]
    return DesktopSession(
        status="ready",
        base_url=base_url,
        worktree_path=worktree_path,
        instructions=steps,
        takeover_supported=True,
        created_at=now,
        notes="Desktop session prepared for human or computer-use agent takeover",
    )


def session_to_dict(session: DesktopSession) -> dict[str, Any]:
    return {
        "status": session.status,
        "base_url": session.base_url,
        "worktree_path": session.worktree_path,
        "instructions": session.instructions,
        "takeover_supported": session.takeover_supported,
        "created_at": session.created_at,
        "notes": session.notes,
    }
