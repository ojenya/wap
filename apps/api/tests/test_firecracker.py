"""Firecracker microVM backend tests (emulated without /dev/kvm)."""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings
from app.environments import create_environment, refresh_environment
from app.models import EnvBackend, EnvironmentStatus, VmStatus
from app.vm.backends import FirecrackerBackend, LocalBackend
from app.vm.capabilities import detect_capabilities
from app.vm.firecracker_api import FirecrackerApi
from app.vm.manager import VmManager


def test_capabilities_prefer_firecracker_emulate(monkeypatch):
    monkeypatch.setenv("APP_FIRECRACKER_MODE", "emulate")
    get_settings.cache_clear()
    try:
        caps = detect_capabilities()
        assert caps.preferred_backend == "firecracker"
        assert caps.can_emulate is True
        assert caps.can_boot_real is False
    finally:
        get_settings.cache_clear()


def test_firecracker_api_emulator_snapshot_files(tmp_path: Path):
    sock = tmp_path / "fc.sock"
    api = FirecrackerApi(socket_path=sock, emulate=True)
    api.configure_boot(
        kernel_path=str(tmp_path / "vmlinux"),
        boot_args="console=ttyS0",
        rootfs_path=str(tmp_path / "rootfs.ext4"),
        vcpu_count=2,
        mem_size_mib=512,
    )
    api.start_instance()
    mem = tmp_path / "mem"
    vmstate = tmp_path / "vmstate"
    api.pause()
    api.create_snapshot(mem, vmstate)
    assert mem.exists() and vmstate.exists()
    assert any(c["path"] == "/actions" for c in api._emu_state["calls"])


def test_manager_boot_snapshot_restore_destroy(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("APP_FIRECRACKER_MODE", "emulate")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    try:
        env = create_environment(
            db_session,
            name="fc-env",
            backend="firecracker",
            update_script="true",
        )
        ws = tmp_path / "src"
        ws.mkdir()
        (ws / "hello.txt").write_text("hi", encoding="utf-8")

        mgr = VmManager(db_session)
        vm = mgr.boot(env, workspace_src=ws)
        assert vm.status == VmStatus.running
        assert vm.backend == EnvBackend.firecracker
        assert (Path(vm.workspace_path) / "hello.txt").read_text(encoding="utf-8") == "hi"
        assert vm.meta.get("emulated") is True

        env.snapshot_id = "snap-test"
        vm = mgr.snapshot(vm, env)
        assert Path(vm.snapshot_path or "").exists()
        assert (Path(vm.snapshot_path) / "mem").exists()

        mgr.destroy(vm, env)
        assert vm.status == VmStatus.destroyed

        restored = mgr.restore(env, workspace_src=ws)
        assert restored.status == VmStatus.running
        assert restored.meta.get("emulated") is True
        mgr.destroy(restored, env)
    finally:
        get_settings.cache_clear()


def test_refresh_environment_uses_firecracker_snapshot(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("APP_FIRECRACKER_MODE", "emulate")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    try:
        env = create_environment(
            db_session,
            name="refresh-fc",
            backend="firecracker",
            update_script="true\necho ok",
        )
        refreshed = refresh_environment(db_session, env)
        assert refreshed.status == EnvironmentStatus.ready
        assert refreshed.snapshot_id
        assert "booted instance=" in refreshed.last_refresh_log
        assert "OK snapshot=" in refreshed.last_refresh_log
    finally:
        get_settings.cache_clear()


def test_api_vm_lifecycle(client, tmp_path, monkeypatch):
    monkeypatch.setenv("APP_FIRECRACKER_MODE", "emulate")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    try:
        caps = client.get("/api/environments/capabilities")
        assert caps.status_code == 200
        assert caps.json()["preferred_backend"] == "firecracker"

        env = client.post(
            "/api/environments",
            json={
                "name": "api-fc",
                "backend": "firecracker",
                "update_script": "true",
            },
        )
        assert env.status_code == 201
        env_id = env.json()["id"]
        assert env.json()["backend"] == "firecracker"

        boot = client.post(f"/api/environments/{env_id}/vms/boot", json={})
        assert boot.status_code == 201
        vm_id = boot.json()["id"]
        assert boot.json()["status"] == "running"
        assert boot.json()["backend"] == "firecracker"

        snap = client.post(f"/api/environments/{env_id}/vms/{vm_id}/snapshot")
        assert snap.status_code == 200
        assert snap.json()["snapshot_path"]

        exe = client.post(
            f"/api/environments/{env_id}/vms/{vm_id}/exec",
            json={"command": ["bash", "-lc", "echo hello-from-vm"]},
        )
        assert exe.status_code == 200
        assert exe.json()["exit_code"] == 0
        assert "hello-from-vm" in exe.json()["output"]

        shot = client.post(f"/api/environments/{env_id}/vms/{vm_id}/screenshot")
        assert shot.status_code == 200
        assert shot.json()["filename"].endswith(".png")
        assert Path(shot.json()["path"]).is_file()
        latest = client.get(f"/api/environments/{env_id}/vms/{vm_id}/screenshot/latest")
        assert latest.status_code == 200
        assert latest.headers["content-type"].startswith("image/png")

        destroy = client.post(f"/api/environments/{env_id}/vms/{vm_id}/destroy")
        assert destroy.status_code == 200
        assert destroy.json()["status"] == "destroyed"

        deleted = client.delete(f"/api/environments/{env_id}")
        assert deleted.status_code == 204
        assert client.get(f"/api/environments/{env_id}").status_code == 404
    finally:
        get_settings.cache_clear()


def test_delete_environment_removes_disk_state(db_session, tmp_path, monkeypatch):
    from app.environments import delete_environment

    monkeypatch.setenv("APP_FIRECRACKER_MODE", "emulate")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    try:
        env = create_environment(
            db_session,
            name="to-delete",
            backend="firecracker",
            update_script="true",
        )
        mgr = VmManager(db_session)
        vm = mgr.boot(env)
        work = Path(vm.work_dir)
        staging = tmp_path / "data" / "env-staging" / env.id
        staging.mkdir(parents=True)
        (staging / "x").write_text("1", encoding="utf-8")
        assert work.exists()

        delete_environment(db_session, env)
        assert db_session.get(type(env), env.id) is None
        assert not work.exists()
        assert not staging.exists()
    finally:
        get_settings.cache_clear()


def test_local_backend_isolates_workspace(tmp_path: Path):
    backend = LocalBackend()
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("x", encoding="utf-8")
    work = tmp_path / "vm"
    result = backend.boot(
        instance_id="local1",
        work_dir=work,
        workspace_src=src,
        vcpu_count=1,
        mem_size_mib=256,
    )
    assert (result.workspace_path / "a.txt").exists()
    code, out = backend.exec(work, ["bash", "-lc", "echo ok"])
    assert code == 0 and "ok" in out
    snap = backend.snapshot(work, tmp_path / "snap")
    assert (snap / "workspace" / "a.txt").exists()
    backend.destroy(work, None)
    assert not work.exists()


def test_firecracker_backend_emulate_boot(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("APP_FIRECRACKER_MODE", "emulate")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        caps = detect_capabilities(settings)
        backend = FirecrackerBackend(settings, caps)
        work = tmp_path / "fc"
        result = backend.boot(
            instance_id="fc1",
            work_dir=work,
            workspace_src=None,
            vcpu_count=2,
            mem_size_mib=512,
        )
        assert result.emulate is True
        assert result.meta["backend"] == "firecracker"
        snap = backend.snapshot(work, tmp_path / "snap")
        assert (snap / "mem").exists()
        backend.destroy(work, result.pid)
    finally:
        get_settings.cache_clear()
