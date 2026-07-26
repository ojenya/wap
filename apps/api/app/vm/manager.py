"""Orchestrate VM lifecycle: boot / snapshot / restore / destroy."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import EnvBackend, Environment, VmInstance, VmStatus
from app.vm.backends import FirecrackerBackend, LocalBackend, VmBackendError
from app.vm.capabilities import VmCapabilities, detect_capabilities


def _now() -> datetime:
    return datetime.now(UTC)


class VmManager:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.caps = detect_capabilities(self.settings)
        self.root = Path(self.settings.data_dir).resolve() / "vms"
        self.root.mkdir(parents=True, exist_ok=True)
        self.snapshots_root = Path(self.settings.data_dir).resolve() / "vm-snapshots"
        self.snapshots_root.mkdir(parents=True, exist_ok=True)

    def capabilities(self) -> VmCapabilities:
        return self.caps

    def _pick_backend(self, env: Environment) -> tuple[str, LocalBackend | FirecrackerBackend]:
        """Choose backend. Env.backend=firecracker prefers FC (real or emulate)."""
        if self.settings.firecracker_mode == "local" or env.backend == EnvBackend.local:
            return "local", LocalBackend()
        if env.backend == EnvBackend.firecracker:
            if self.caps.mode == "require" and not self.caps.can_boot_real:
                raise VmBackendError(self.caps.reason)
            return "firecracker", FirecrackerBackend(self.settings, self.caps)
        return "local", LocalBackend()

    def boot(
        self,
        env: Environment,
        *,
        run_id: str | None = None,
        workspace_src: str | Path | None = None,
        restore_snapshot: bool = False,
    ) -> VmInstance:
        backend_name, backend = self._pick_backend(env)
        instance = VmInstance(
            environment_id=env.id,
            run_id=run_id,
            backend=EnvBackend(backend_name),
            status=VmStatus.creating,
        )
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)

        work_dir = self.root / instance.id
        snap_path: Path | None = None
        if restore_snapshot and env.snapshot_id:
            candidate = self.snapshots_root / env.id / env.snapshot_id
            if candidate.exists():
                snap_path = candidate
                instance.status = VmStatus.restoring
                self.db.commit()

        try:
            result = backend.boot(
                instance_id=instance.id,
                work_dir=work_dir,
                workspace_src=Path(workspace_src) if workspace_src else None,
                vcpu_count=env.vcpu_count or 2,
                mem_size_mib=env.mem_size_mib or 1024,
                snapshot_to_restore=snap_path,
            )
        except Exception as exc:  # noqa: BLE001
            instance.status = VmStatus.error
            instance.last_error = str(exc)
            instance.updated_at = _now()
            self.db.commit()
            self.db.refresh(instance)
            raise VmBackendError(str(exc)) from exc

        instance.work_dir = str(result.work_dir)
        instance.workspace_path = str(result.workspace_path)
        instance.socket_path = str(result.socket_path)
        instance.pid = result.pid
        instance.guest_ip = result.guest_ip
        instance.rootfs_path = str(result.rootfs_path) if result.rootfs_path else None
        instance.snapshot_path = str(snap_path) if snap_path else None
        instance.meta = result.meta
        instance.status = VmStatus.running
        instance.last_error = None
        instance.updated_at = _now()
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def snapshot(self, instance: VmInstance, env: Environment) -> VmInstance:
        if instance.status not in {VmStatus.running, VmStatus.paused}:
            raise VmBackendError(f"cannot snapshot instance in status={instance.status}")
        _, backend = self._pick_backend(env)
        instance.status = VmStatus.snapshotting
        self.db.commit()

        snap_id = env.snapshot_id or f"snap-{instance.id[:8]}"
        snap_dir = self.snapshots_root / env.id / snap_id
        try:
            backend.snapshot(Path(instance.work_dir), snap_dir)
        except Exception as exc:  # noqa: BLE001
            instance.status = VmStatus.error
            instance.last_error = str(exc)
            instance.updated_at = _now()
            self.db.commit()
            raise VmBackendError(str(exc)) from exc

        env.snapshot_id = snap_id
        instance.snapshot_path = str(snap_dir)
        instance.status = VmStatus.running
        instance.updated_at = _now()
        env.updated_at = _now()
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def restore(
        self,
        env: Environment,
        *,
        run_id: str | None = None,
        workspace_src: str | Path | None = None,
    ) -> VmInstance:
        if not env.snapshot_id:
            raise VmBackendError("environment has no snapshot_id to restore")
        return self.boot(
            env,
            run_id=run_id,
            workspace_src=workspace_src,
            restore_snapshot=True,
        )

    def destroy(self, instance: VmInstance, env: Environment | None = None) -> VmInstance:
        env = env or self.db.get(Environment, instance.environment_id)
        if env is None:
            raise VmBackendError("environment missing")
        _, backend = self._pick_backend(env)
        try:
            backend.destroy(Path(instance.work_dir), instance.pid)
        except Exception as exc:  # noqa: BLE001
            instance.last_error = str(exc)
        instance.status = VmStatus.destroyed
        instance.pid = None
        instance.updated_at = _now()
        self.db.commit()
        self.db.refresh(instance)
        return instance

    def exec(
        self, instance: VmInstance, env: Environment, command: list[str], timeout: int = 120
    ) -> tuple[int, str]:
        if instance.status != VmStatus.running:
            raise VmBackendError(f"instance not running ({instance.status})")
        _, backend = self._pick_backend(env)
        return backend.exec(Path(instance.work_dir), command, timeout=timeout)

    def list_instances(self, environment_id: str | None = None) -> list[VmInstance]:
        q = select(VmInstance).order_by(VmInstance.created_at.desc())
        if environment_id:
            q = q.where(VmInstance.environment_id == environment_id)
        return list(self.db.scalars(q))

    def get_instance(self, instance_id: str) -> VmInstance | None:
        return self.db.get(VmInstance, instance_id)
