#!/usr/bin/env python3
"""Host-side privileged helper for safe unplug operations.

Run this service on the host (as root via systemd). The Dockerized web app can
call it when direct unmount is permission-blocked.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import shutil
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

LOG = logging.getLogger("headphones-unplug-helper")

BIND = os.getenv("HELPER_BIND", "127.0.0.1")
PORT = int(os.getenv("HELPER_PORT", "17888"))
TOKEN = os.getenv("HELPER_TOKEN", "").strip()
CONFIG_PATH = Path(
    os.getenv("HELPER_CONFIG_PATH", "/home/alfonso/.music-ferry/config.yaml")
).expanduser()
ALLOWED_MOUNT_OVERRIDE = os.getenv("HELPER_ALLOWED_MOUNT", "").strip()
ALLOWED_MOUNT: Path | None = None


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _normalize_path(value: str | Path) -> Path:
    return Path(os.path.normpath(str(Path(value).expanduser())))


def _extract_headphones_mount_from_yaml(config_path: Path) -> Path | None:
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    in_paths = False
    paths_indent = 0

    for raw_line in lines:
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if stripped == "paths:":
            in_paths = True
            paths_indent = indent
            continue

        if in_paths and indent <= paths_indent:
            in_paths = False

        if in_paths and stripped.startswith("headphones_mount:"):
            value = stripped.split(":", 1)[1].strip()
            if not value:
                return None
            if (
                (value.startswith("\"") and value.endswith("\""))
                or (value.startswith("'") and value.endswith("'"))
            ) and len(value) >= 2:
                value = value[1:-1]
            return _normalize_path(value)

    return None


def _load_allowed_mount() -> Path:
    if ALLOWED_MOUNT_OVERRIDE:
        return _normalize_path(ALLOWED_MOUNT_OVERRIDE)

    from_yaml = _extract_headphones_mount_from_yaml(CONFIG_PATH)
    if from_yaml is not None:
        return from_yaml

    raise RuntimeError(
        "Could not determine allowed mount path. Set HELPER_ALLOWED_MOUNT or "
        f"ensure paths.headphones_mount exists in {CONFIG_PATH}."
    )


def _is_allowed_mount(mount_path: Path) -> bool:
    if ALLOWED_MOUNT is None:
        return False
    return _normalize_path(mount_path) == ALLOWED_MOUNT


def _is_real_mounted(mount_path: Path) -> bool:
    result = _run(["findmnt", "-rn", "--target", str(mount_path), "-o", "FSTYPE"])
    if result.returncode != 0:
        return False
    fstypes = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return any(fstype != "autofs" for fstype in fstypes)


def _mount_source(mount_path: Path) -> str | None:
    result = _run(["findmnt", "-rn", "--target", str(mount_path), "-o", "SOURCE"])
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        source = line.strip()
        if source and source != "systemd-1":
            return source
    return None


def prepare_unplug(mount_path: Path) -> dict[str, Any]:
    os.sync()
    if not _is_real_mounted(mount_path):
        return {
            "ok": True,
            "synced": True,
            "unmounted": True,
            "message": f"No active filesystem mount at {mount_path}. Safe to unplug.",
        }

    result = _run(["umount", str(mount_path)])
    if result.returncode == 0 and not _is_real_mounted(mount_path):
        return {
            "ok": True,
            "synced": True,
            "unmounted": True,
            "message": f"Unmounted {mount_path}. Safe to unplug.",
        }

    source = _mount_source(mount_path)
    if source and source.startswith("/dev/") and shutil.which("udisksctl"):
        udisks = _run(["udisksctl", "unmount", "-b", source])
        if udisks.returncode == 0 and not _is_real_mounted(mount_path):
            return {
                "ok": True,
                "synced": True,
                "unmounted": True,
                "message": (
                    f"Unmounted {mount_path} via udisksctl ({source}). Safe to unplug."
                ),
            }
        udisks_err = (udisks.stderr or udisks.stdout or "").strip()
        return {
            "ok": False,
            "synced": True,
            "unmounted": False,
            "message": (
                f"Could not unmount {mount_path} with udisksctl ({source}): "
                f"{udisks_err or 'unknown error'}"
            ),
        }

    umount_err = (result.stderr or result.stdout or "").strip()
    return {
        "ok": False,
        "synced": True,
        "unmounted": False,
        "message": (
            f"Could not unmount {mount_path}: {umount_err or 'unknown error'}"
        ),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "MusicFerryUnplugHelper/1.1"

    def _reply(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/prepare-unplug":
            self._reply(404, {"ok": False, "message": "Not found"})
            return

        provided_token = self.headers.get("X-Music-Ferry-Token", "").strip()
        if not hmac.compare_digest(provided_token, TOKEN):
            self._reply(403, {"ok": False, "message": "Forbidden"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._reply(400, {"ok": False, "message": "Invalid Content-Length"})
            return

        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._reply(400, {"ok": False, "message": "Invalid JSON payload"})
            return

        mount_path_raw = str(payload.get("mount_path") or "").strip()
        if not mount_path_raw:
            self._reply(400, {"ok": False, "message": "mount_path is required"})
            return

        mount_path = _normalize_path(mount_path_raw)
        if not _is_allowed_mount(mount_path):
            self._reply(
                400,
                {
                    "ok": False,
                    "message": (
                        f"mount_path '{mount_path}' is not allowed. "
                        f"Allowed mount: {ALLOWED_MOUNT}"
                    ),
                },
            )
            return

        LOG.info("prepare-unplug requested for %s", mount_path)
        result = prepare_unplug(mount_path)
        status = 200 if result.get("ok") else 409
        self._reply(status, result)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._reply(
                200,
                {
                    "ok": True,
                    "status": "healthy",
                    "allowed_mount": str(ALLOWED_MOUNT or ""),
                },
            )
            return
        self._reply(404, {"ok": False, "message": "Not found"})

    def log_message(self, fmt: str, *args: Any) -> None:
        LOG.info("%s - %s", self.address_string(), fmt % args)


def main() -> None:
    global ALLOWED_MOUNT

    logging.basicConfig(
        level=os.getenv("HELPER_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    if not TOKEN:
        raise RuntimeError("HELPER_TOKEN must be set. Refusing to start without auth.")

    ALLOWED_MOUNT = _load_allowed_mount()

    LOG.info(
        "Starting helper on %s:%s (allowed mount: %s, config: %s)",
        BIND,
        PORT,
        ALLOWED_MOUNT,
        CONFIG_PATH,
    )
    with ThreadingHTTPServer((BIND, PORT), Handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
