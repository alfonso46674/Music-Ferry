# music_ferry/web/services/sync_service.py
"""Service for managing background sync operations."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import FastAPI

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


class SyncService:
    """Manages background sync operations."""

    def __init__(self, app: FastAPI):
        self.app = app
        self._lock = asyncio.Lock()
        self._current_job: SyncJob | None = None
        self._job_history: dict[str, SyncJob] = {}
        self._last_sync_time: str | None = None
        self._max_history = 10

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

    async def _run_sync(
        self,
        job: SyncJob,
        sync_spotify: bool,
        sync_youtube: bool,
    ) -> None:
        """Run the actual sync operation."""
        from music_ferry.orchestrator import Orchestrator

        config = self.app.state.config

        try:
            orchestrator = Orchestrator(config)
            result = await orchestrator.run(
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


# Singleton instance per app
_sync_services: dict[int, SyncService] = {}


def get_sync_service(app: FastAPI) -> SyncService:
    """Get or create the SyncService for an app."""
    app_id = id(app)
    if app_id not in _sync_services:
        _sync_services[app_id] = SyncService(app)
    return _sync_services[app_id]
