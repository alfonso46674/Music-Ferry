# music_ferry/web/services/sync_service.py
"""Service for managing background sync operations."""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI

from music_ferry.config import Config
from music_ferry.notify import SyncResult

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Status of a sync job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SyncJob:
    """Represents a sync job."""

    job_id: str
    status: JobStatus = JobStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class SyncSchedule:
    """Persistent scheduler settings for automatic sync runs."""

    enabled: bool = False
    time: str = "05:00"  # HH:MM (24-hour local time)
    source: str = "youtube"  # all | spotify | youtube


class SyncService:
    """Manages background sync operations."""

    def __init__(self, app: FastAPI):
        self.app = app
        self._lock = asyncio.Lock()
        self._current_job: SyncJob | None = None
        self._job_history: dict[str, SyncJob] = {}
        self._last_sync_time: str | None = None
        self._max_history = 10
        self._schedule_file = self._get_schedule_file()
        self._schedule = self._load_schedule()
        self._scheduler_task: asyncio.Task[None] | None = None
        self._scheduler_stop_event = asyncio.Event()
        self._last_scheduled_run_date: date | None = None
        self._next_scheduled_time: datetime | None = None

    @property
    def is_syncing(self) -> bool:
        """Check if a sync is currently in progress."""
        return (
            self._current_job is not None
            and self._current_job.status == JobStatus.RUNNING
        )

    @property
    def last_sync_time(self) -> str | None:
        """Get the timestamp of the last completed sync."""
        return self._last_sync_time

    @property
    def current_job_id(self) -> str | None:
        """Get the ID of the currently running job."""
        if self._current_job and self._current_job.status == JobStatus.RUNNING:
            return self._current_job.job_id
        return None

    @property
    def next_scheduled_time(self) -> str | None:
        """Get the next scheduled run time in ISO format."""
        if not self._schedule.enabled:
            return None
        if self._next_scheduled_time is None:
            self._next_scheduled_time = self._compute_next_scheduled_time()
        next_time = self._next_scheduled_time
        if next_time is None:
            return None
        return next_time.isoformat()

    async def start_sync(
        self,
        sync_spotify: bool = True,
        sync_youtube: bool = True,
    ) -> str | None:
        """Start a new sync operation.

        Returns job_id if started, None if already syncing.
        """
        async with self._lock:
            if self.is_syncing:
                return None

            job_id = str(uuid.uuid4())[:8]
            job = SyncJob(
                job_id=job_id,
                status=JobStatus.RUNNING,
                started_at=datetime.now(),
            )
            self._current_job = job
            self._job_history[job_id] = job

        # Start sync in background task
        asyncio.create_task(self._run_sync(job, sync_spotify, sync_youtube))

        return job_id

    async def start_scheduler(self) -> None:
        """Start the background scheduler loop if not already running."""
        if self._scheduler_task is not None and not self._scheduler_task.done():
            return

        self._scheduler_stop_event.clear()
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Sync scheduler started")

    async def stop_scheduler(self) -> None:
        """Stop the background scheduler loop."""
        if self._scheduler_task is None:
            return

        self._scheduler_stop_event.set()
        try:
            await self._scheduler_task
        except asyncio.CancelledError:
            pass
        finally:
            self._scheduler_task = None
        logger.info("Sync scheduler stopped")

    def get_schedule(self) -> dict[str, Any]:
        """Return scheduler configuration and computed next run."""
        if self._schedule.enabled:
            self._next_scheduled_time = self._compute_next_scheduled_time()
        else:
            self._next_scheduled_time = None

        return {
            "enabled": self._schedule.enabled,
            "time": self._schedule.time,
            "source": self._schedule.source,
            "next_run": (
                self._next_scheduled_time.isoformat()
                if self._next_scheduled_time is not None
                else None
            ),
        }

    def update_schedule(
        self,
        *,
        enabled: bool,
        time: str,
        source: str,
    ) -> dict[str, Any]:
        """Update and persist scheduler settings."""
        normalized_time = self._normalize_time(time)
        normalized_source = self._normalize_source(source)

        self._schedule.enabled = bool(enabled)
        self._schedule.time = normalized_time
        self._schedule.source = normalized_source
        self._save_schedule()
        self._next_scheduled_time = self._compute_next_scheduled_time()
        logger.info(
            "Schedule updated: enabled=%s time=%s source=%s",
            self._schedule.enabled,
            self._schedule.time,
            self._schedule.source,
        )
        return self.get_schedule()

    async def _run_sync(
        self,
        job: SyncJob,
        sync_spotify: bool,
        sync_youtube: bool,
    ) -> None:
        """Run the actual sync operation."""
        config = self.app.state.config

        try:
            # Run orchestration in a worker thread to keep the web event loop responsive.
            result = await asyncio.to_thread(
                self._run_orchestrator_blocking,
                config,
                sync_spotify=sync_spotify,
                sync_youtube=sync_youtube,
            )

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            job.result = {
                "total_tracks": result.total_tracks,
                "is_success": result.is_success,
                "has_errors": result.has_errors,
                "playlists": [
                    {
                        "name": p.name,
                        "tracks_synced": p.tracks_synced,
                        "error": p.error,
                    }
                    for p in result.playlists
                ],
            }
            self._last_sync_time = job.completed_at.isoformat()

            logger.info(
                f"Sync job {job.job_id} completed: {result.total_tracks} tracks"
            )

        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now()
            job.error = str(e)
            logger.exception(f"Sync job {job.job_id} failed: {e}")

        finally:
            async with self._lock:
                self._current_job = None
                self._cleanup_history()

    def _run_orchestrator_blocking(
        self,
        config: Config,
        *,
        sync_spotify: bool,
        sync_youtube: bool,
    ) -> SyncResult:
        """Run orchestrator coroutine on a dedicated event loop in a worker thread."""
        from music_ferry.orchestrator import Orchestrator

        orchestrator = Orchestrator(config)
        return asyncio.run(
            orchestrator.run(
                sync_spotify=sync_spotify,
                sync_youtube=sync_youtube,
            )
        )

    async def _scheduler_loop(self) -> None:
        """Run scheduled syncs based on persisted UI settings."""
        while not self._scheduler_stop_event.is_set():
            if not self._schedule.enabled:
                self._next_scheduled_time = None
                await self._wait_for_scheduler(15.0)
                continue

            next_scheduled_time = self._compute_next_scheduled_time()
            if next_scheduled_time is None:
                self._next_scheduled_time = None
                await self._wait_for_scheduler(15.0)
                continue

            self._next_scheduled_time = next_scheduled_time
            now = datetime.now()
            seconds_until_due = (next_scheduled_time - now).total_seconds()

            if seconds_until_due > 0:
                await self._wait_for_scheduler(min(seconds_until_due, 15.0))
                continue

            sync_spotify, sync_youtube = self._schedule_source_flags()
            job_id = await self.start_sync(
                sync_spotify=sync_spotify,
                sync_youtube=sync_youtube,
            )
            if job_id is not None:
                self._last_scheduled_run_date = datetime.now().date()
                logger.info("Scheduled sync started (job=%s)", job_id)
            else:
                logger.info(
                    "Scheduled sync due but sync already running; retrying shortly"
                )

            await self._wait_for_scheduler(10.0)

    async def _wait_for_scheduler(self, timeout_seconds: float) -> None:
        """Wait with stop-event support."""
        try:
            await asyncio.wait_for(
                self._scheduler_stop_event.wait(),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            return

    def _compute_next_scheduled_time(self) -> datetime | None:
        """Compute the next scheduled run in local time."""
        if not self._schedule.enabled:
            return None

        hour, minute = self._parse_time(self._schedule.time)
        now = datetime.now()
        today_target = now.replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
        )

        if self._last_scheduled_run_date == now.date():
            return today_target + timedelta(days=1)
        if now <= today_target:
            return today_target
        return today_target + timedelta(days=1)

    def _schedule_source_flags(self) -> tuple[bool, bool]:
        """Map schedule source selection to sync flags."""
        source = self._schedule.source
        if source == "spotify":
            return True, False
        if source == "youtube":
            return False, True
        return True, True

    def _get_schedule_file(self) -> Path:
        """Location of scheduler settings persisted by the web UI."""
        config = cast(Config, self.app.state.config)
        return config.paths.music_dir / "web_schedule.json"

    def _load_schedule(self) -> SyncSchedule:
        """Read schedule from disk; fall back to defaults if missing/invalid."""
        if not self._schedule_file.exists():
            return SyncSchedule()

        try:
            raw = json.loads(self._schedule_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning(
                "Failed to read %s; using default schedule settings",
                self._schedule_file,
            )
            return SyncSchedule()

        enabled = bool(raw.get("enabled", False))
        time = self._normalize_time(str(raw.get("time", "05:00")))
        source = self._normalize_source(str(raw.get("source", "youtube")))
        return SyncSchedule(enabled=enabled, time=time, source=source)

    def _save_schedule(self) -> None:
        """Persist schedule settings to disk."""
        self._schedule_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "enabled": self._schedule.enabled,
            "time": self._schedule.time,
            "source": self._schedule.source,
        }
        self._schedule_file.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _normalize_time(self, value: str) -> str:
        """Validate and normalize HH:MM schedule value."""
        hour, minute = self._parse_time(value)
        return f"{hour:02d}:{minute:02d}"

    def _parse_time(self, value: str) -> tuple[int, int]:
        """Parse HH:MM value and return hour/minute ints."""
        parts = value.split(":", maxsplit=1)
        if len(parts) != 2:
            raise ValueError("Time must use HH:MM format.")

        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError as exc:
            raise ValueError("Time must use HH:MM format.") from exc

        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("Time must be between 00:00 and 23:59.")

        return hour, minute

    def _normalize_source(self, value: str) -> str:
        """Validate schedule source option."""
        source = value.strip().lower()
        if source not in {"all", "spotify", "youtube"}:
            raise ValueError("Source must be one of: all, spotify, youtube.")
        return source

    def _cleanup_history(self) -> None:
        """Remove old jobs from history."""
        if len(self._job_history) > self._max_history:
            # Sort by start time and keep only recent jobs
            sorted_jobs = sorted(
                self._job_history.items(),
                key=lambda x: x[1].started_at or datetime.min,
                reverse=True,
            )
            self._job_history = dict(sorted_jobs[: self._max_history])

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get the status of a specific job."""
        job = self._job_history.get(job_id)
        if job is None:
            return None

        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "progress": job.progress,
            "result": job.result,
            "error": job.error,
        }


def get_sync_service(app: FastAPI) -> SyncService:
    """Get or create the SyncService for an app."""
    existing = getattr(app.state, "sync_service", None)
    if isinstance(existing, SyncService):
        return existing

    service = SyncService(app)
    app.state.sync_service = service
    return service
