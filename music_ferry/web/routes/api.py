# music_ferry/web/routes/api.py
"""REST API endpoints for Music Ferry web UI."""

import logging
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/status")
async def get_status(request: Request) -> dict[str, Any]:
    """Get current sync status.

    Returns sync state, last sync time, and next scheduled sync.
    """
    from music_ferry.web.services.sync_service import get_sync_service

    sync_service = get_sync_service(request.app)
    return {
        "syncing": sync_service.is_syncing,
        "last_sync": sync_service.last_sync_time,
        "next_scheduled": None,  # No scheduler implemented yet
        "current_job_id": sync_service.current_job_id,
    }


@router.get("/library")
async def get_library_summary(request: Request) -> dict[str, Any]:
    """Get library summary for all sources."""
    from music_ferry.web.services.library_service import LibraryService

    config = request.app.state.config
    service = LibraryService(config)
    return service.get_summary()


@router.get("/library/{source}")
async def get_library_detail(source: str, request: Request) -> dict[str, Any]:
    """Get detailed library info for a specific source."""
    from music_ferry.web.services.library_service import LibraryService

    config = request.app.state.config
    service = LibraryService(config)
    return service.get_detail(source)


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    """Get sanitized configuration (secrets redacted)."""
    from music_ferry.web.services.library_service import LibraryService

    config = request.app.state.config
    service = LibraryService(config)
    return service.get_sanitized_config()


@router.post("/sync")
async def trigger_sync(request: Request) -> dict[str, Any]:
    """Trigger a sync operation.

    Returns a job_id that can be used to track progress.
    """
    from music_ferry.web.services.sync_service import get_sync_service

    sync_service = get_sync_service(request.app)
    job_id = await sync_service.start_sync()

    if job_id is None:
        return {
            "error": "Sync already in progress",
            "current_job_id": sync_service.current_job_id,
        }

    return {"job_id": job_id, "status": "started"}


@router.get("/sync/{job_id}")
async def get_sync_status(job_id: str, request: Request) -> dict[str, Any]:
    """Get status of a specific sync job."""
    from music_ferry.web.services.sync_service import get_sync_service

    sync_service = get_sync_service(request.app)
    status = sync_service.get_job_status(job_id)

    if status is None:
        return {"error": "Job not found", "job_id": job_id}

    return status
