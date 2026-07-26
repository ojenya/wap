"""MCP registry API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Operator, Viewer
from app.db import get_db
from app.mcp_registry import discover_tools, invoke_tool, list_servers, register_server
from app.models import McpServer, McpTransport

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


class McpServerIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    transport: str = "http"
    url: str = ""
    command: str = ""
    enabled: bool = True


class McpServerOut(BaseModel):
    id: str
    name: str
    transport: str
    url: str
    command: str
    enabled: bool
    tools_cache: list
    created_at: str


class InvokeIn(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


def _out(s: McpServer) -> McpServerOut:
    return McpServerOut(
        id=s.id,
        name=s.name,
        transport=s.transport.value,
        url=s.url,
        command=s.command,
        enabled=s.enabled,
        tools_cache=list(s.tools_cache or []),
        created_at=s.created_at.isoformat(),
    )


@router.get("/servers", response_model=list[McpServerOut])
def get_servers(_: Viewer, db: Session = Depends(get_db)) -> list[McpServerOut]:
    return [_out(s) for s in list_servers(db)]


@router.post("/servers", response_model=McpServerOut, status_code=201)
def create_server(payload: McpServerIn, _: Operator, db: Session = Depends(get_db)) -> McpServerOut:
    try:
        transport = McpTransport(payload.transport)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid transport") from exc
    server = register_server(
        db,
        name=payload.name,
        transport=transport,
        url=payload.url,
        command=payload.command,
        enabled=payload.enabled,
    )
    return _out(server)


@router.post("/servers/{server_id}/discover", response_model=McpServerOut)
def discover(server_id: str, _: Operator, db: Session = Depends(get_db)) -> McpServerOut:
    server = db.get(McpServer, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    discover_tools(db, server)
    return _out(server)


@router.post("/servers/{server_id}/invoke")
def invoke(
    server_id: str, payload: InvokeIn, _: Operator, db: Session = Depends(get_db)
) -> dict:
    server = db.get(McpServer, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    return invoke_tool(db, server, payload.tool, payload.arguments)
