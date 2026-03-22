"""Service for discovering and transferring to headphone mount points."""

from __future__ import annotations

import copy
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from music_ferry.config import Config
from music_ferry.transfer import InteractiveTransfer

logger = logging.getLogger(__name__)


class HeadphonesService:
    """Service for headphone mount discovery, access checks, and transfers."""

    SCAN_ROOTS = (Path("/run/media"), Path("/media"), Path("/mnt"))

    def __init__(self, config: Config):
        self.config = config
        self.music_folder_name = config.paths.headphones_music_folder

    def scan_devices(self) -> dict[str, Any]:
        """Scan likely mount points and report accessibility details."""
        configured_mount = self.config.paths.headphones_mount
        mount_table = self._read_mount_table()
        candidates = self._iter_candidate_mounts(mount_table)
        devices = [
            self._describe_mount(mount, mount_table.get(mount, []))
            for mount in sorted(candidates)
        ]

        devices.sort(
            key=lambda device: (
                not device["is_configured"],
                not device["connected"],
                not device["accessible"],
                device["mount_path"],
            )
        )

        return {
            "configured_mount": str(configured_mount),
            "music_folder": self.music_folder_name,
            "devices": devices,
        }

    def ensure_access(self, mount_path: str | None) -> dict[str, Any]:
        """Ensure the headphones music folder exists and is writable."""
        mount = self._normalize_mount_path(mount_path)
        if not mount.exists() or not mount.is_dir():
            device = self._describe_mount(mount)
            return {
                "ok": False,
                "message": f"Mount path does not exist: {mount}",
                "device": device,
            }

        music_path = mount / self.music_folder_name
        try:
            music_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Failed to create music folder at %s: %s", music_path, exc)
            device = self._describe_mount(mount)
            return {
                "ok": False,
                "message": f"Failed to create music folder: {exc}",
                "device": device,
            }

        probe_file = music_path / ".music-ferry-write-test"
        try:
            probe_file.write_text("ok", encoding="utf-8")
            probe_file.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Write access check failed for %s: %s", music_path, exc)
            device = self._describe_mount(mount)
            return {
                "ok": False,
                "message": f"Path is not writable: {exc}",
                "device": device,
            }

        device = self._describe_mount(mount)
        return {
            "ok": device["accessible"],
            "message": (
                f"Headphones path is accessible at {device['music_path']}"
                if device["accessible"]
                else "Headphones path still not accessible"
            ),
            "device": device,
        }

    def transfer_to_mount(
        self,
        mount_path: str | None,
        source: str = "all",
    ) -> dict[str, Any]:
        """Transfer selected source tracks to a chosen mount path."""
        mount = self._normalize_mount_path(mount_path)
        self._validate_mount_path(mount)

        source = source.lower().strip()
        if source == "all":
            sources = ["spotify", "youtube"]
        elif source in {"spotify", "youtube"}:
            sources = [source]
        else:
            raise ValueError("Invalid transfer source. Use all, spotify, or youtube.")

        transfer_config = copy.deepcopy(self.config)
        transfer_config.paths.headphones_mount = mount
        transfer = InteractiveTransfer(
            transfer_config,
            sources=sources,
            auto=True,
        )

        if not transfer.is_mounted():
            device = self._describe_mount(mount)
            return {
                "ok": False,
                "message": (
                    f"Headphones not mounted or missing '{self.music_folder_name}' "
                    f"folder at {mount}"
                ),
                "device": device,
            }

        before_status = transfer.compute_status()
        copied, removed = transfer.sync_changes(auto=True)
        status = transfer.compute_status()
        message = f"Transfer complete: {copied} copied, {removed} removed."
        if copied == 0 and removed == 0 and before_status.new_to_transfer == 0:
            message = (
                "Headphones already up to date: "
                f"{status.headphones_track_count}/{status.local_track_count} "
                "tracked tracks present."
            )
        elif copied == 0 and before_status.new_to_transfer > 0:
            message = (
                "Transfer finished but copied 0 tracks. "
                "Check free space and reserve settings."
            )

        device = self._describe_mount(mount)
        return {
            "ok": True,
            "message": message,
            "copied": copied,
            "removed": removed,
            "before": {
                "local_track_count": before_status.local_track_count,
                "headphones_track_count": before_status.headphones_track_count,
                "new_to_transfer": before_status.new_to_transfer,
                "orphaned_on_headphones": before_status.orphaned_on_headphones,
            },
            "status": {
                "local_track_count": status.local_track_count,
                "headphones_track_count": status.headphones_track_count,
                "new_to_transfer": status.new_to_transfer,
                "orphaned_on_headphones": status.orphaned_on_headphones,
            },
            "device": device,
        }

    def delete_mp3_files(self, mount_path: str | None) -> dict[str, Any]:
        """Delete MP3 files from selected headphones music path safely."""
        mount = self._normalize_mount_path(mount_path)
        self._validate_mount_path(mount)

        if not self._is_real_mounted(mount):
            return {
                "ok": False,
                "message": f"Headphones are not mounted at {mount}.",
                "deleted": 0,
                "bytes_freed": 0,
            }

        music_path = mount / self.music_folder_name
        if not music_path.exists() or not music_path.is_dir():
            return {
                "ok": False,
                "message": f"Music path not found: {music_path}",
                "deleted": 0,
                "bytes_freed": 0,
            }

        deleted = 0
        bytes_freed = 0
        for file_path in music_path.glob("*.mp3"):
            try:
                if file_path.is_file():
                    size = file_path.stat().st_size
                    file_path.unlink()
                    deleted += 1
                    bytes_freed += size
            except OSError as exc:
                logger.warning("Failed deleting %s: %s", file_path, exc)

        os.sync()
        return {
            "ok": True,
            "message": f"Deleted {deleted} MP3 file(s) from {music_path}.",
            "deleted": deleted,
            "bytes_freed": bytes_freed,
        }

    def prepare_unplug(self, mount_path: str | None) -> dict[str, Any]:
        """Flush writes and attempt unmount so device can be safely unplugged."""
        mount = self._normalize_mount_path(mount_path)
        self._validate_prepare_unplug_target(mount)
        self._validate_mount_path(mount)

        logger.info("Prepare-unplug requested for %s", mount)
        os.sync()
        logger.info("Filesystem sync completed for %s", mount)

        if not self._is_real_mounted(mount):
            logger.info("No active real mount found at %s; safe to unplug", mount)
            return {
                "ok": True,
                "synced": True,
                "unmounted": True,
                "message": (
                    f"No active filesystem mount detected at {mount}. "
                    "Safe to unplug."
                ),
            }

        result = subprocess.run(
            ["umount", str(mount)],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0 and not self._is_real_mounted(mount):
            logger.info("Unmounted %s directly from container process", mount)
            return {
                "ok": True,
                "synced": True,
                "unmounted": True,
                "message": f"Unmounted {mount}. Safe to unplug.",
            }

        stderr = (result.stderr or "").strip()
        logger.warning(
            "Direct unmount failed for %s (rc=%s): %s",
            mount,
            result.returncode,
            stderr or "unknown error",
        )

        helper_result = self._try_helper_prepare_unplug(mount)
        if helper_result is not None:
            return helper_result

        if "permission denied" in stderr.lower() or "not permitted" in stderr.lower():
            hint = (
                "Unmount requires host permissions in this Docker setup. "
                "Use the desktop eject action on this device."
            )
        else:
            hint = (
                "Device is synced but still mounted. "
                "Please unmount/eject from the host before unplugging."
            )

        return {
            "ok": False,
            "synced": True,
            "unmounted": False,
            "message": (
                f"Could not unmount {mount}: {stderr or 'unknown error'}. {hint}"
            ),
        }

    def _validate_prepare_unplug_target(self, mount: Path) -> None:
        """Allow prepare-unplug only for the configured headphones mount."""
        configured = self.config.paths.headphones_mount
        if mount != configured:
            raise ValueError(
                "Prepare safe unplug is restricted to configured headphones mount: "
                f"{configured}"
            )

    def _try_helper_prepare_unplug(self, mount: Path) -> dict[str, Any] | None:
        """Try host-side helper service for privileged unmount (optional)."""
        helper_url = os.getenv("MUSIC_FERRY_UNPLUG_HELPER_URL", "").strip()
        if not helper_url:
            return None

        endpoint = f"{helper_url.rstrip('/')}/prepare-unplug"
        token = os.getenv("MUSIC_FERRY_UNPLUG_HELPER_TOKEN", "").strip()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Music-Ferry-Token"] = token

        payload = json.dumps({"mount_path": str(mount)}).encode("utf-8")
        request = urlrequest.Request(
            endpoint,
            data=payload,
            headers=headers,
            method="POST",
        )

        logger.info("Attempting host helper prepare-unplug via %s", endpoint)

        try:
            with urlrequest.urlopen(request, timeout=15) as response:
                raw = response.read().decode("utf-8")
        except urlerror.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.warning(
                "Host helper HTTP error for %s: status=%s body=%s",
                mount,
                exc.code,
                body,
            )
            return {
                "ok": False,
                "synced": True,
                "unmounted": False,
                "message": (
                    f"Host helper rejected prepare-unplug for {mount} "
                    f"(HTTP {exc.code})."
                ),
            }
        except OSError as exc:
            logger.warning("Host helper call failed for %s: %s", mount, exc)
            return {
                "ok": False,
                "synced": True,
                "unmounted": False,
                "message": (
                    f"Could not reach host helper for {mount}: {exc}. "
                    "Use desktop eject action."
                ),
            }

        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            logger.warning("Host helper returned non-JSON response: %r", raw)
            return {
                "ok": False,
                "synced": True,
                "unmounted": False,
                "message": (
                    "Host helper returned an invalid response. "
                    "Use desktop eject action."
                ),
            }

        helper_ok = bool(data.get("ok"))
        helper_message = str(data.get("message") or "").strip()
        if helper_ok and not self._is_real_mounted(mount):
            logger.info("Host helper unmounted %s successfully", mount)
            return {
                "ok": True,
                "synced": True,
                "unmounted": True,
                "message": helper_message or f"Unmounted {mount}. Safe to unplug.",
            }

        logger.warning(
            "Host helper did not complete unmount for %s: ok=%s message=%s",
            mount,
            helper_ok,
            helper_message or "none",
        )
        return {
            "ok": False,
            "synced": True,
            "unmounted": False,
            "message": (
                helper_message
                or (
                    f"Host helper could not unmount {mount}. "
                    "Use desktop eject action."
                )
            ),
        }

    def _read_mount_table(self) -> dict[Path, list[tuple[str, str]]]:
        """Read /proc/mounts and map mount paths to (source, fstype) entries."""
        table: dict[Path, list[tuple[str, str]]] = {}
        mounts_file = Path("/proc/mounts")
        if not mounts_file.exists():
            return table

        try:
            for line in mounts_file.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) < 3:
                    continue
                source = parts[0]
                mount = Path(parts[1].replace("\\040", " "))
                fstype = parts[2]
                if not mount.is_absolute():
                    continue
                table.setdefault(mount, []).append((source, fstype))
        except OSError:
            logger.debug("Unable to read /proc/mounts", exc_info=True)

        return table

    def _is_real_mounted(self, mount: Path) -> bool:
        """Return true when mount has a non-autofs backing filesystem entry."""
        entries = self._read_mount_table().get(mount, [])
        return any(fstype != "autofs" for _, fstype in entries)

    def _iter_candidate_mounts(
        self,
        mount_table: dict[Path, list[tuple[str, str]]],
    ) -> set[Path]:
        """Collect candidate mount paths from config and mount table."""
        candidates: set[Path] = {self.config.paths.headphones_mount}
        for mount in mount_table:
            if self._is_scannable_mount(mount):
                candidates.add(mount)
        return {path for path in candidates if path.is_absolute()}

    def _describe_mount(
        self,
        mount: Path,
        mount_entries: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Describe mount accessibility and readiness for transfer."""
        entries = mount_entries or []
        has_real_mount = any(fstype != "autofs" for _, fstype in entries)
        has_autofs_only = bool(entries) and not has_real_mount

        if has_autofs_only:
            # Avoid touching autofs-only paths during background scans: stat/access
            # can trigger mount attempts even when the backing device is absent.
            music_path = mount / self.music_folder_name
            return {
                "name": mount.name or str(mount),
                "mount_path": str(mount),
                "music_path": str(music_path),
                "connected": False,
                "accessible": False,
                "music_folder_exists": False,
                "can_prepare": False,
                "is_configured": mount == self.config.paths.headphones_mount,
                "reason": "Automount waiting for device",
            }

        mount_exists = mount.exists() and mount.is_dir()
        mount_readable = mount_exists and os.access(mount, os.R_OK | os.X_OK)
        mount_writable = mount_exists and os.access(mount, os.W_OK | os.X_OK)

        music_path = mount / self.music_folder_name
        music_exists = music_path.exists() and music_path.is_dir()
        music_readable = music_exists and os.access(music_path, os.R_OK | os.X_OK)
        music_writable = music_exists and os.access(music_path, os.W_OK | os.X_OK)

        accessible = (
            mount_exists
            and mount_readable
            and (
                (music_exists and music_readable and music_writable)
                or (not music_exists and mount_writable)
            )
        )

        if not mount_exists:
            reason = "Mount path not found"
        elif not mount_readable:
            reason = "Mount path is not readable"
        elif music_exists and not (music_readable and music_writable):
            reason = "Music folder is not readable/writable"
        elif not music_exists and not mount_writable:
            reason = "Mount path is not writable (cannot create music folder)"
        elif not music_exists:
            reason = f"Music folder '{self.music_folder_name}' is missing"
        else:
            reason = "Ready"

        return {
            "name": mount.name or str(mount),
            "mount_path": str(mount),
            "music_path": str(music_path),
            "connected": mount_exists,
            "accessible": accessible,
            "music_folder_exists": music_exists,
            "can_prepare": mount_exists and mount_writable,
            "is_configured": mount == self.config.paths.headphones_mount,
            "reason": reason,
        }

    def _normalize_mount_path(self, mount_path: str | None) -> Path:
        """Parse and validate mount path input."""
        if not mount_path:
            return self.config.paths.headphones_mount

        mount = Path(mount_path).expanduser()
        if not mount.is_absolute():
            raise ValueError("Mount path must be absolute.")
        return mount

    def _validate_mount_path(self, mount: Path) -> None:
        """Restrict transfer targets to known mount roots or configured mount."""
        if mount == self.config.paths.headphones_mount:
            return

        for root in self.SCAN_ROOTS:
            if root == mount or root in mount.parents:
                return

        raise ValueError(
            "Mount path is outside supported roots (/media, /run/media, /mnt)."
        )

    def _is_scannable_mount(self, mount: Path) -> bool:
        """Check if a mount path is under configured scan roots."""
        if mount == self.config.paths.headphones_mount:
            return True

        for root in self.SCAN_ROOTS:
            if root == mount or root in mount.parents:
                return True

        return False
