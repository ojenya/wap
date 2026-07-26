"""MCP server registry + tool invoke contracts."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import McpServer, McpTransport


def list_servers(db: Session) -> list[McpServer]:
    return list(db.scalars(select(McpServer).order_by(McpServer.created_at.desc())))


def register_server(
    db: Session,
    *,
    name: str,
    transport: McpTransport = McpTransport.http,
    url: str = "",
    command: str = "",
    enabled: bool = True,
) -> McpServer:
    existing = db.scalar(select(McpServer).where(McpServer.name == name))
    if existing:
        existing.transport = transport
        existing.url = url
        existing.command = command
        existing.enabled = enabled
        db.commit()
        db.refresh(existing)
        return existing
    server = McpServer(
        name=name,
        transport=transport,
        url=url,
        command=command,
        enabled=enabled,
        tools_cache=_default_tools(name),
    )
    db.add(server)
    db.commit()
    db.refresh(server)
    return server


def _default_tools(name: str) -> list[dict[str, Any]]:
    return [
        {
            "name": f"{name}.ping",
            "description": f"Health check for MCP server '{name}'",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": f"{name}.search",
            "description": "Generic search tool stub",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    ]


def discover_tools(db: Session, server: McpServer) -> list[dict[str, Any]]:
    """Refresh tool cache. Real MCP handshake is an extension seam."""
    server.tools_cache = _default_tools(server.name)
    db.commit()
    db.refresh(server)
    return list(server.tools_cache or [])


def invoke_tool(
    db: Session,
    server: McpServer,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not server.enabled:
        return {"ok": False, "error": "server disabled"}
    tools = {t["name"]: t for t in (server.tools_cache or [])}
    if tool_name not in tools and not tool_name.endswith(".ping"):
        # Allow refresh-then-retry for known default ping.
        discover_tools(db, server)
        tools = {t["name"]: t for t in (server.tools_cache or [])}
    if tool_name not in tools:
        return {"ok": False, "error": f"unknown tool: {tool_name}"}
    args = arguments or {}
    if tool_name.endswith(".ping"):
        return {
            "ok": True,
            "content": [{"type": "text", "text": f"pong from {server.name}"}],
            "transport": server.transport.value,
        }
    if tool_name.endswith(".search"):
        q = str(args.get("query", ""))
        return {
            "ok": True,
            "content": [
                {
                    "type": "text",
                    "text": f"[{server.name}] search stub results for: {q}",
                }
            ],
        }
    return {"ok": True, "content": [{"type": "text", "text": "ok"}], "arguments": args}
