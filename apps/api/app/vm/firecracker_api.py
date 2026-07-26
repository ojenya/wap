"""Minimal Firecracker HTTP API client (unix socket) + emulator for CI."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass, field
from http.client import HTTPConnection
from pathlib import Path
from typing import Any
from urllib.parse import quote


class FirecrackerApiError(RuntimeError):
    pass


class _UnixHTTPConnection(HTTPConnection):
    def __init__(self, path: str, timeout: float = 10.0) -> None:
        super().__init__("localhost", timeout=timeout)
        self._unix_path = path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self._unix_path)
        self.sock = sock


@dataclass
class FirecrackerApi:
    """Talk to a running Firecracker process via its API socket."""

    socket_path: Path
    emulate: bool = False
    _emu_state: dict[str, Any] = field(default_factory=dict)

    def put(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("PUT", path, body)

    def patch(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("PATCH", path, body)

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path, None)

    def configure_boot(
        self,
        *,
        kernel_path: str,
        boot_args: str,
        rootfs_path: str,
        vcpu_count: int,
        mem_size_mib: int,
    ) -> None:
        self.put(
            "/boot-source",
            {"kernel_image_path": kernel_path, "boot_args": boot_args},
        )
        self.put(
            "/drives/rootfs",
            {
                "drive_id": "rootfs",
                "path_on_host": rootfs_path,
                "is_root_device": True,
                "is_read_only": False,
            },
        )
        self.put(
            "/machine-config",
            {
                "vcpu_count": vcpu_count,
                "mem_size_mib": mem_size_mib,
                "smt": False,
            },
        )

    def start_instance(self) -> None:
        self.put("/actions", {"action_type": "InstanceStart"})

    def pause(self) -> None:
        self.patch("/vm", {"state": "Paused"})

    def resume(self) -> None:
        self.patch("/vm", {"state": "Resumed"})

    def create_snapshot(self, mem_file: Path, vmstate_file: Path) -> None:
        self.put(
            "/snapshot/create",
            {
                "snapshot_type": "Full",
                "snapshot_path": str(vmstate_file),
                "mem_file_path": str(mem_file),
            },
        )

    def load_snapshot(self, mem_file: Path, vmstate_file: Path) -> None:
        self.put(
            "/snapshot/load",
            {
                "snapshot_path": str(vmstate_file),
                "mem_backend": {
                    "backend_type": "File",
                    "backend_path": str(mem_file),
                },
                "enable_diff_snapshots": False,
                "resume_vm": True,
            },
        )

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None
    ) -> dict[str, Any]:
        if self.emulate:
            return self._emulate(method, path, body)
        conn = _UnixHTTPConnection(str(self.socket_path))
        payload = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        try:
            conn.request(method, quote(path), body=payload, headers=headers)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            if resp.status >= 400:
                raise FirecrackerApiError(
                    f"{method} {path} -> {resp.status}: {data or raw}"
                )
            return data if isinstance(data, dict) else {"result": data}
        except OSError as exc:
            raise FirecrackerApiError(f"socket error on {self.socket_path}: {exc}") from exc
        finally:
            conn.close()

    def _emulate(
        self, method: str, path: str, body: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Record Firecracker API calls without a real VMM (CI / no KVM)."""
        self._emu_state.setdefault("calls", []).append(
            {"method": method, "path": path, "body": body}
        )
        if path == "/actions" and (body or {}).get("action_type") == "InstanceStart":
            self._emu_state["running"] = True
        if path == "/vm":
            self._emu_state["vm_state"] = (body or {}).get("state")
        if path == "/snapshot/create":
            mem = Path((body or {}).get("mem_file_path", "mem"))
            vmstate = Path((body or {}).get("snapshot_path", "vmstate"))
            mem.parent.mkdir(parents=True, exist_ok=True)
            mem.write_bytes(b"FC_MEM_EMU")
            vmstate.write_bytes(b"FC_VMSTATE_EMU")
            self._emu_state["snapshot"] = {
                "mem": str(mem),
                "vmstate": str(vmstate),
            }
        if path == "/snapshot/load":
            self._emu_state["running"] = True
            self._emu_state["restored"] = True
        return {"emulated": True}
