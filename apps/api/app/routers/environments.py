"""Environment CRUD + Firecracker VM lifecycle."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import Operator, Viewer
from app.db import get_db
from app.environments import (
    create_environment,
    delete_environment,
    list_environments,
    refresh_environment,
)
from app.models import Environment, VmInstance
from app.vm.backends import VmBackendError
from app.vm.manager import VmManager

router = APIRouter(prefix="/api/environments", tags=["environments"])


class EnvironmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    repository_id: str | None = None
    update_script: str = "pnpm install\npip install -e ."
    dockerfile_path: str = ".cursor/Dockerfile"
    agents_md_path: str = "AGENTS.md"
    backend: str = "firecracker"
    vcpu_count: int = 2
    mem_size_mib: int = 1024


class EnvironmentOut(BaseModel):
    id: str
    name: str
    repository_id: str | None
    dockerfile_path: str
    environment_json_path: str
    update_script: str
    agents_md_path: str
    backend: str
    vcpu_count: int
    mem_size_mib: int
    snapshot_id: str | None
    status: str
    last_refresh_log: str
    last_error: str | None
    created_at: str
    updated_at: str


class VmInstanceOut(BaseModel):
    id: str
    environment_id: str
    run_id: str | None
    backend: str
    status: str
    work_dir: str
    workspace_path: str
    socket_path: str
    pid: int | None
    guest_ip: str | None
    snapshot_path: str | None
    rootfs_path: str | None
    last_error: str | None
    meta: dict
    created_at: str
    updated_at: str


class BootIn(BaseModel):
    run_id: str | None = None
    workspace_src: str | None = None
    restore_snapshot: bool = False


class ExecIn(BaseModel):
    command: list[str] = Field(min_length=1)
    timeout: int = 120


def _env_out(env: Environment) -> EnvironmentOut:
    return EnvironmentOut(
        id=env.id,
        name=env.name,
        repository_id=env.repository_id,
        dockerfile_path=env.dockerfile_path,
        environment_json_path=env.environment_json_path,
        update_script=env.update_script,
        agents_md_path=env.agents_md_path,
        backend=env.backend.value if hasattr(env.backend, "value") else str(env.backend),
        vcpu_count=env.vcpu_count,
        mem_size_mib=env.mem_size_mib,
        snapshot_id=env.snapshot_id,
        status=env.status.value,
        last_refresh_log=env.last_refresh_log,
        last_error=env.last_error,
        created_at=env.created_at.isoformat(),
        updated_at=env.updated_at.isoformat(),
    )


def _vm_out(vm: VmInstance) -> VmInstanceOut:
    return VmInstanceOut(
        id=vm.id,
        environment_id=vm.environment_id,
        run_id=vm.run_id,
        backend=vm.backend.value,
        status=vm.status.value,
        work_dir=vm.work_dir,
        workspace_path=vm.workspace_path,
        socket_path=vm.socket_path,
        pid=vm.pid,
        guest_ip=vm.guest_ip,
        snapshot_path=vm.snapshot_path,
        rootfs_path=vm.rootfs_path,
        last_error=vm.last_error,
        meta=vm.meta or {},
        created_at=vm.created_at.isoformat(),
        updated_at=vm.updated_at.isoformat(),
    )


@router.get("/capabilities")
def vm_capabilities(_: Viewer, db: Session = Depends(get_db)) -> dict:
    caps = VmManager(db).capabilities()
    return {
        "kvm": caps.kvm,
        "firecracker_bin": caps.firecracker_bin,
        "kernel": caps.kernel,
        "rootfs": caps.rootfs,
        "mode": caps.mode,
        "can_boot_real": caps.can_boot_real,
        "can_emulate": caps.can_emulate,
        "preferred_backend": caps.preferred_backend,
        "reason": caps.reason,
    }


@router.get("", response_model=list[EnvironmentOut])
def list_envs(_: Viewer, db: Session = Depends(get_db)) -> list[EnvironmentOut]:
    return [_env_out(e) for e in list_environments(db)]


@router.post("", response_model=EnvironmentOut, status_code=201)
def create_env(
    payload: EnvironmentIn, _: Operator, db: Session = Depends(get_db)
) -> EnvironmentOut:
    env = create_environment(
        db,
        name=payload.name,
        repository_id=payload.repository_id,
        update_script=payload.update_script,
        dockerfile_path=payload.dockerfile_path,
        agents_md_path=payload.agents_md_path,
        backend=payload.backend,
        vcpu_count=payload.vcpu_count,
        mem_size_mib=payload.mem_size_mib,
    )
    return _env_out(env)


@router.post("/{env_id}/refresh", response_model=EnvironmentOut)
def refresh_env(env_id: str, _: Operator, db: Session = Depends(get_db)) -> EnvironmentOut:
    env = db.get(Environment, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return _env_out(refresh_environment(db, env))


@router.delete("/{env_id}", status_code=204)
def delete_env(env_id: str, _: Operator, db: Session = Depends(get_db)) -> None:
    env = db.get(Environment, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    delete_environment(db, env)


@router.get("/{env_id}", response_model=EnvironmentOut)
def get_env(env_id: str, _: Viewer, db: Session = Depends(get_db)) -> EnvironmentOut:
    env = db.get(Environment, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return _env_out(env)


@router.get("/{env_id}/vms", response_model=list[VmInstanceOut])
def list_vms(env_id: str, _: Viewer, db: Session = Depends(get_db)) -> list[VmInstanceOut]:
    if db.get(Environment, env_id) is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return [_vm_out(v) for v in VmManager(db).list_instances(env_id)]


@router.post("/{env_id}/vms/boot", response_model=VmInstanceOut, status_code=201)
def boot_vm(
    env_id: str, payload: BootIn, _: Operator, db: Session = Depends(get_db)
) -> VmInstanceOut:
    env = db.get(Environment, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    try:
        vm = VmManager(db).boot(
            env,
            run_id=payload.run_id,
            workspace_src=payload.workspace_src,
            restore_snapshot=payload.restore_snapshot,
        )
    except VmBackendError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _vm_out(vm)


@router.post("/{env_id}/vms/{vm_id}/snapshot", response_model=VmInstanceOut)
def snapshot_vm(
    env_id: str, vm_id: str, _: Operator, db: Session = Depends(get_db)
) -> VmInstanceOut:
    env = db.get(Environment, env_id)
    vm = db.get(VmInstance, vm_id)
    if env is None or vm is None or vm.environment_id != env_id:
        raise HTTPException(status_code=404, detail="VM not found")
    try:
        return _vm_out(VmManager(db).snapshot(vm, env))
    except VmBackendError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{env_id}/vms/restore", response_model=VmInstanceOut, status_code=201)
def restore_vm(
    env_id: str, payload: BootIn, _: Operator, db: Session = Depends(get_db)
) -> VmInstanceOut:
    env = db.get(Environment, env_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    try:
        vm = VmManager(db).restore(
            env, run_id=payload.run_id, workspace_src=payload.workspace_src
        )
    except VmBackendError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _vm_out(vm)


@router.post("/{env_id}/vms/{vm_id}/destroy", response_model=VmInstanceOut)
def destroy_vm(
    env_id: str, vm_id: str, _: Operator, db: Session = Depends(get_db)
) -> VmInstanceOut:
    env = db.get(Environment, env_id)
    vm = db.get(VmInstance, vm_id)
    if env is None or vm is None or vm.environment_id != env_id:
        raise HTTPException(status_code=404, detail="VM not found")
    try:
        return _vm_out(VmManager(db).destroy(vm, env))
    except VmBackendError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{env_id}/vms/{vm_id}/exec")
def exec_vm(
    env_id: str,
    vm_id: str,
    payload: ExecIn,
    _: Operator,
    db: Session = Depends(get_db),
) -> dict:
    env = db.get(Environment, env_id)
    vm = db.get(VmInstance, vm_id)
    if env is None or vm is None or vm.environment_id != env_id:
        raise HTTPException(status_code=404, detail="VM not found")
    try:
        code, out = VmManager(db).exec(vm, env, payload.command, timeout=payload.timeout)
    except VmBackendError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"exit_code": code, "output": out[:8000]}


@router.post("/{env_id}/vms/{vm_id}/screenshot")
def screenshot_vm(
    env_id: str, vm_id: str, _: Operator, db: Session = Depends(get_db)
) -> dict:
    """Capture a workspace preview PNG (not a guest desktop framebuffer)."""
    env = db.get(Environment, env_id)
    vm = db.get(VmInstance, vm_id)
    if env is None or vm is None or vm.environment_id != env_id:
        raise HTTPException(status_code=404, detail="VM not found")
    try:
        path = VmManager(db).screenshot(vm)
    except VmBackendError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "path": str(path),
        "url": f"/api/environments/{env_id}/vms/{vm_id}/screenshot/latest",
        "filename": path.name,
    }


@router.get("/{env_id}/vms/{vm_id}/screenshot/latest")
def latest_screenshot(
    env_id: str, vm_id: str, _: Viewer, db: Session = Depends(get_db)
) -> FileResponse:
    vm = db.get(VmInstance, vm_id)
    if vm is None or vm.environment_id != env_id:
        raise HTTPException(status_code=404, detail="VM not found")
    path_str = (vm.meta or {}).get("last_screenshot")
    if not path_str:
        raise HTTPException(status_code=404, detail="No screenshot yet")
    path = Path(path_str)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Screenshot file missing")
    return FileResponse(path, media_type="image/png", filename=path.name)
