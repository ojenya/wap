"""Detect host support for Firecracker microVMs."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings, get_settings


@dataclass(frozen=True)
class VmCapabilities:
    kvm: bool
    firecracker_bin: str | None
    kernel: str | None
    rootfs: str | None
    mode: str
    can_boot_real: bool
    can_emulate: bool
    preferred_backend: str  # firecracker | local
    reason: str


def detect_capabilities(settings: Settings | None = None) -> VmCapabilities:
    settings = settings or get_settings()
    mode = settings.firecracker_mode
    kvm = Path("/dev/kvm").exists() and os.access("/dev/kvm", os.R_OK | os.W_OK)
    binary = shutil.which(settings.firecracker_bin) or (
        settings.firecracker_bin
        if Path(settings.firecracker_bin).is_file()
        else None
    )
    kernel = settings.firecracker_kernel or None
    if kernel and not Path(kernel).is_file():
        kernel = None
    rootfs = settings.firecracker_rootfs or None
    if rootfs and not Path(rootfs).is_file():
        rootfs = None

    can_boot_real = bool(kvm and binary and kernel and rootfs)

    if mode == "local":
        return VmCapabilities(
            kvm=kvm,
            firecracker_bin=binary,
            kernel=kernel,
            rootfs=rootfs,
            mode=mode,
            can_boot_real=False,
            can_emulate=False,
            preferred_backend="local",
            reason="APP_FIRECRACKER_MODE=local",
        )
    if mode == "require":
        if can_boot_real:
            return VmCapabilities(
                kvm=kvm,
                firecracker_bin=binary,
                kernel=kernel,
                rootfs=rootfs,
                mode=mode,
                can_boot_real=True,
                can_emulate=False,
                preferred_backend="firecracker",
                reason="KVM + firecracker + kernel + rootfs available",
            )
        missing = []
        if not kvm:
            missing.append("/dev/kvm")
        if not binary:
            missing.append("firecracker binary")
        if not kernel:
            missing.append("kernel image (APP_FIRECRACKER_KERNEL)")
        if not rootfs:
            missing.append("rootfs (APP_FIRECRACKER_ROOTFS)")
        return VmCapabilities(
            kvm=kvm,
            firecracker_bin=binary,
            kernel=kernel,
            rootfs=rootfs,
            mode=mode,
            can_boot_real=False,
            can_emulate=False,
            preferred_backend="firecracker",
            reason="missing: " + ", ".join(missing),
        )
    if mode == "emulate" or (mode == "auto" and not can_boot_real):
        return VmCapabilities(
            kvm=kvm,
            firecracker_bin=binary,
            kernel=kernel,
            rootfs=rootfs,
            mode="emulate" if mode == "emulate" else mode,
            can_boot_real=can_boot_real,
            can_emulate=True,
            preferred_backend="firecracker",
            reason=(
                "emulating Firecracker API lifecycle (no KVM/assets)"
                if not can_boot_real
                else "emulate mode forced"
            ),
        )
    # auto + can_boot_real
    return VmCapabilities(
        kvm=kvm,
        firecracker_bin=binary,
        kernel=kernel,
        rootfs=rootfs,
        mode=mode,
        can_boot_real=True,
        can_emulate=True,
        preferred_backend="firecracker",
        reason="KVM + firecracker + kernel + rootfs available",
    )
