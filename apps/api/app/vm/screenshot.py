"""Capture a VM workspace screenshot (emulate-friendly, no guest desktop required)."""

from __future__ import annotations

import html
import struct
import zlib
from datetime import UTC, datetime
from pathlib import Path


def _png_rgb(width: int, height: int, pixels: bytes) -> bytes:
    """Encode raw RGB bytes (len = width*height*3) as a PNG."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + pixels[y * width * 3 : (y + 1) * width * 3] for y in range(height))
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(raw, 9)),
            chunk(b"IEND", b""),
        ]
    )


def _fill(buf: bytearray, w: int, h: int, color: tuple[int, int, int]) -> None:
    r, g, b = color
    for i in range(0, w * h * 3, 3):
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b


def _put_pixel(buf: bytearray, w: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    if x < 0 or y < 0 or x >= w:
        return
    idx = (y * w + x) * 3
    if idx < 0 or idx + 2 >= len(buf):
        return
    buf[idx], buf[idx + 1], buf[idx + 2] = color


# Tiny 5x7 bitmap font for A-Z, 0-9, and a few punctuation marks.
_FONT: dict[str, list[str]] = {
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    "/": ["00001", "00010", "00100", "01000", "10000", "00000", "00000"],
    "_": ["00000", "00000", "00000", "00000", "00000", "00000", "11111"],
    "=": ["00000", "00000", "11111", "00000", "11111", "00000", "00000"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11100", "10010", "10001", "10001", "10001", "10010", "11100"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10001", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10001", "10101", "11011", "10001"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
}


def _draw_text(
    buf: bytearray,
    w: int,
    x: int,
    y: int,
    text: str,
    color: tuple[int, int, int],
    scale: int = 2,
) -> None:
    cx = x
    for ch in text.upper():
        glyph = _FONT.get(ch) or _FONT.get("?") or _FONT[" "]
        for row, bits in enumerate(glyph):
            for col, bit in enumerate(bits):
                if bit != "1":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        _put_pixel(buf, w, cx + col * scale + dx, y + row * scale + dy, color)
        cx += 6 * scale


def render_workspace_png(
    *,
    title: str,
    lines: list[str],
    width: int = 960,
    height: int = 540,
) -> bytes:
    """Draw a simple desktop-like PNG summarizing the VM workspace."""
    buf = bytearray(width * height * 3)
    _fill(buf, width, height, (24, 28, 36))
    # Top bar
    for y in range(0, 48):
        for x in range(width):
            _put_pixel(buf, width, x, y, (36, 42, 54))
    _draw_text(buf, width, 24, 16, title[:48], (230, 232, 238), scale=2)
    y = 72
    for line in lines[:18]:
        _draw_text(buf, width, 24, y, line[:70], (180, 190, 200), scale=2)
        y += 22
        if y > height - 30:
            break
    return _png_rgb(width, height, bytes(buf))


def _list_workspace(workspace: Path, limit: int = 40) -> list[str]:
    if not workspace.exists():
        return ["(workspace missing)"]
    entries: list[str] = []
    for path in sorted(workspace.rglob("*")):
        if path.is_file():
            rel = path.relative_to(workspace).as_posix()
            entries.append(rel)
            if len(entries) >= limit:
                entries.append("...")
                break
    return entries or ["(empty workspace)"]


def capture_vm_screenshot(
    *,
    instance_id: str,
    workspace_path: str,
    artifacts_root: Path,
    backend: str,
    status: str,
) -> Path:
    """Write a PNG under artifacts/vms/<id>/ and return its path."""
    workspace = Path(workspace_path)
    out_dir = artifacts_root / "vms" / instance_id
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = out_dir / f"screenshot-{stamp}.png"

    files = _list_workspace(workspace)
    lines = [
        f"vm: {instance_id[:8]}",
        f"backend: {backend}  status: {status}",
        f"workspace: {workspace.name}",
        "files:",
        *[f"- {f}" for f in files[:16]],
    ]
    # Prefer Playwright HTML capture when Chromium is available (richer preview).
    try:
        from playwright.sync_api import sync_playwright

        body = "".join(f"<li>{html.escape(f)}</li>" for f in files[:40])
        page_html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>
body{{margin:0;font:14px/1.4 ui-monospace,monospace;background:#181c24;color:#e6e8ee}}
header{{padding:16px 20px;background:#242a36;border-bottom:1px solid #333}}
main{{padding:20px}} ul{{columns:2;gap:24px}}
</style></head><body>
<header><strong>WAP VM screenshot</strong> · {html.escape(instance_id[:8])}
 · {html.escape(backend)} · {html.escape(status)}</header>
<main><p>Workspace files</p><ul>{body}</ul></main></body></html>"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 960, "height": 540})
            page.set_content(page_html, wait_until="domcontentloaded")
            page.screenshot(path=str(out), full_page=False)
            browser.close()
        return out
    except Exception:  # noqa: BLE001 — fall back to pure-Python PNG
        out.write_bytes(
            render_workspace_png(title=f"WAP VM {instance_id[:8]}", lines=lines)
        )
        return out
