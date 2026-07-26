"""Concrete environment backends: local jail + Firecracker microVM."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.config import Settings
from app.vm.capabilities import VmCapabilities
from app.vm.firecracker_api import FirecrackerApi, FirecrackerApiError


class VmBackendError(RuntimeError):
    pass


@dataclass
class BootResult:
    work_dir: Path
    workspace_path: Path
    socket_path: Path
    pid: int | None
    guest_ip: str | None
    rootfs_path: Path | None
    emulate: bool
    meta: dict


class EnvBackendImpl(Protocol):
    name: str

    def boot(
        self,
        *,
        instance_id: str,
        work_dir: Path,
        workspace_src: Path | None,
        vcpu_count: int,
        mem_size_mib: int,
        snapshot_to_restore: Path | None = None,
    ) -> BootResult: ...

    def snapshot(self, work_dir: Path, snapshot_dir: Path) -> Path: ...

    def destroy(self, work_dir: Path, pid: int | None) -> None: ...

    def exec(self, work_dir: Path, command: list[str], timeout: int = 120) -> tuple[int, str]: ...


class LocalBackend:
    """Process-local jail: isolated work directory, no hypervisor."""

    name = "local"

    def boot(
        self,
        *,
        instance_id: str,
        work_dir: Path,
        workspace_src: Path | None,
        vcpu_count: int,
        mem_size_mib: int,
        snapshot_to_restore: Path | None = None,
    ) -> BootResult:
        work_dir.mkdir(parents=True, exist_ok=True)
        workspace = work_dir / "workspace"
        if snapshot_to_restore and snapshot_to_restore.exists():
            if workspace.exists():
                shutil.rmtree(workspace)
            shutil.copytree(snapshot_to_restore / "workspace", workspace)
        else:
            workspace.mkdir(exist_ok=True)
            if workspace_src and workspace_src.exists():
                # Copy tree (not symlink) so the jail owns a mutable workspace.
                for item in workspace_src.iterdir():
                    dest = workspace / item.name
                    if item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(item, dest, symlinks=True)
                    else:
                        shutil.copy2(item, dest)
        meta = {
            "backend": "local",
            "vcpu_count": vcpu_count,
            "mem_size_mib": mem_size_mib,
            "instance_id": instance_id,
        }
        (work_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return BootResult(
            work_dir=work_dir,
            workspace_path=workspace,
            socket_path=work_dir / "local.sock",
            pid=None,
            guest_ip="127.0.0.1",
            rootfs_path=None,
            emulate=False,
            meta=meta,
        )

    def snapshot(self, work_dir: Path, snapshot_dir: Path) -> Path:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        src = work_dir / "workspace"
        dest = snapshot_dir / "workspace"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        (snapshot_dir / "backend").write_text("local", encoding="utf-8")
        return snapshot_dir

    def destroy(self, work_dir: Path, pid: int | None) -> None:
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)

    def exec(self, work_dir: Path, command: list[str], timeout: int = 120) -> tuple[int, str]:
        workspace = work_dir / "workspace"
        proc = subprocess.run(
            command,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


class FirecrackerBackend:
    """Boot Firecracker microVMs (real or emulated API lifecycle)."""

    name = "firecracker"

    def __init__(self, settings: Settings, caps: VmCapabilities) -> None:
        self.settings = settings
        self.caps = caps
        self.emulate = not caps.can_boot_real

    def boot(
        self,
        *,
        instance_id: str,
        work_dir: Path,
        workspace_src: Path | None,
        vcpu_count: int,
        mem_size_mib: int,
        snapshot_to_restore: Path | None = None,
    ) -> BootResult:
        if self.caps.mode == "require" and not self.caps.can_boot_real:
            raise VmBackendError(
                f"Firecracker required but unavailable: {self.caps.reason}"
            )

        work_dir.mkdir(parents=True, exist_ok=True)
        workspace = work_dir / "workspace"
        workspace.mkdir(exist_ok=True)
        if workspace_src and workspace_src.exists() and not any(workspace.iterdir()):
            for item in workspace_src.iterdir():
                dest = workspace / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, symlinks=True)
                else:
                    shutil.copy2(item, dest)

        socket_path = work_dir / "firecracker.sock"
        if socket_path.exists():
            socket_path.unlink()

        rootfs_path: Path | None = None
        pid: int | None = None
        guest_ip = "172.16.0.2"

        if self.emulate:
            # Emulated VMM: create socket placeholder + drive API through emulator.
            socket_path.write_text("", encoding="utf-8")
            api = FirecrackerApi(socket_path=socket_path, emulate=True)
            rootfs_path = work_dir / "rootfs.ext4"
            rootfs_path.write_bytes(b"FC_ROOTFS_EMU")
            kernel = self.caps.kernel or str(work_dir / "vmlinux")
            if not self.caps.kernel:
                Path(kernel).write_bytes(b"FC_KERNEL_EMU")
            if snapshot_to_restore and (snapshot_to_restore / "vmstate").exists():
                api.load_snapshot(
                    snapshot_to_restore / "mem",
                    snapshot_to_restore / "vmstate",
                )
            else:
                api.configure_boot(
                    kernel_path=kernel,
                    boot_args=self.settings.firecracker_boot_args,
                    rootfs_path=str(rootfs_path),
                    vcpu_count=vcpu_count,
                    mem_size_mib=mem_size_mib,
                )
                api.start_instance()
            meta = {
                "backend": "firecracker",
                "emulated": True,
                "calls": api._emu_state.get("calls", []),
                "instance_id": instance_id,
                "vcpu_count": vcpu_count,
                "mem_size_mib": mem_size_mib,
            }
        else:
            assert self.caps.firecracker_bin and self.caps.kernel and self.caps.rootfs
            rootfs_path = work_dir / "rootfs.ext4"
            shutil.copy2(self.caps.rootfs, rootfs_path)
            cmd = [
                self.caps.firecracker_bin,
                "--api-sock",
                str(socket_path),
                "--id",
                instance_id[:16],
            ]
            log_path = work_dir / "firecracker.log"
            log_fh = log_path.open("w", encoding="utf-8")
            proc = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            pid = proc.pid
            self._wait_socket(socket_path, timeout=10.0)
            api = FirecrackerApi(socket_path=socket_path, emulate=False)
            try:
                if snapshot_to_restore and (snapshot_to_restore / "vmstate").exists():
                    api.load_snapshot(
                        snapshot_to_restore / "mem",
                        snapshot_to_restore / "vmstate",
                    )
                else:
                    api.configure_boot(
                        kernel_path=self.caps.kernel,
                        boot_args=self.settings.firecracker_boot_args,
                        rootfs_path=str(rootfs_path),
                        vcpu_count=vcpu_count,
                        mem_size_mib=mem_size_mib,
                    )
                    api.start_instance()
            except FirecrackerApiError:
                self.destroy(work_dir, pid)
                raise
            meta = {
                "backend": "firecracker",
                "emulated": False,
                "instance_id": instance_id,
                "vcpu_count": vcpu_count,
                "mem_size_mib": mem_size_mib,
                "log": str(log_path),
            }

        (work_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return BootResult(
            work_dir=work_dir,
            workspace_path=workspace,
            socket_path=socket_path,
            pid=pid,
            guest_ip=guest_ip,
            rootfs_path=rootfs_path,
            emulate=self.emulate,
            meta=meta,
        )

    def snapshot(self, work_dir: Path, snapshot_dir: Path) -> Path:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        socket_path = work_dir / "firecracker.sock"
        meta = json.loads((work_dir / "meta.json").read_text(encoding="utf-8"))
        emulate = bool(meta.get("emulated"))
        api = FirecrackerApi(socket_path=socket_path, emulate=emulate)
        mem = snapshot_dir / "mem"
        vmstate = snapshot_dir / "vmstate"
        if not emulate:
            api.pause()
        api.create_snapshot(mem, vmstate)
        # Also freeze workspace tree for host-side tooling / local restore.
        ws_src = work_dir / "workspace"
        ws_dest = snapshot_dir / "workspace"
        if ws_dest.exists():
            shutil.rmtree(ws_dest)
        if ws_src.exists():
            shutil.copytree(ws_src, ws_dest)
        (snapshot_dir / "backend").write_text("firecracker", encoding="utf-8")
        if not emulate:
            try:
                api.resume()
            except FirecrackerApiError:
                pass
        return snapshot_dir

    def destroy(self, work_dir: Path, pid: int | None) -> None:
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.2)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)

    def exec(self, work_dir: Path, command: list[str], timeout: int = 120) -> tuple[int, str]:
        # Until vsock/SSH agent lands, exec runs against the host-side workspace
        # mirror that is synced into the instance directory.
        workspace = work_dir / "workspace"
        meta = {}
        meta_path = work_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        prefix = ["# firecracker-emulated" if meta.get("emulated") else "# firecracker"]
        proc = subprocess.run(
            command,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = "\n".join(prefix) + "\n" + (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out

    @staticmethod
    def _wait_socket(path: Path, timeout: float) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if path.exists():
                return
            time.sleep(0.05)
        raise VmBackendError(f"Firecracker API socket not ready: {path}")
