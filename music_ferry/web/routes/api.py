# music_ferry/web/routes/api.py
"""REST API endpoints for Music Ferry web UI."""

import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from music_ferry.web.services.headphones_service import HeadphonesService
from music_ferry.web.services.library_service import LibraryService
from music_ferry.web.services.sync_service import get_sync_service

router = APIRouter()
logger = logging.getLogger(__name__)


class HeadphonesAccessRequest(BaseModel):
    """Request payload for headphone access check/preparation."""

    mount_path: str | None = None


class HeadphonesTransferRequest(BaseModel):
    """Request payload for transfer-to-headphones."""

    mount_path: str | None = None
    source: str = Field(default="all", pattern="^(all|spotify|youtube)$")


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/status")
async def get_status(request: Request) -> dict[str, Any]:
    """Get current sync status.

    Returns sync state, last sync time, and next scheduled sync.
    """

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

    config = request.app.state.config
    service = LibraryService(config)
    return service.get_summary()


@router.get("/library/{source}")
async def get_library_detail(source: str, request: Request) -> dict[str, Any]:
    """Get detailed library info for a specific source."""

    config = request.app.state.config
    service = LibraryService(config)
    return service.get_detail(source)


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    """Get sanitized configuration (secrets redacted)."""

    config = request.app.state.config
    service = LibraryService(config)
    return service.get_sanitized_config()


@router.post("/sync")
async def trigger_sync(request: Request) -> dict[str, Any]:
    """Trigger a sync operation.

    Returns a job_id that can be used to track progress.
    """

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

    sync_service = get_sync_service(request.app)
    status = sync_service.get_job_status(job_id)

    if status is None:
        return {"error": "Job not found", "job_id": job_id}

    return status


@router.get("/headphones/scan")
async def scan_headphones(request: Request) -> dict[str, Any]:
    """Scan for configured and connected headphone mount points."""
    service = HeadphonesService(request.app.state.config)
    return service.scan_devices()


@router.post("/headphones/access")
async def ensure_headphones_access(
    payload: HeadphonesAccessRequest,
    request: Request,
) -> dict[str, Any]:
    """Create/check the music folder so selected headphones are accessible."""

    service = HeadphonesService(request.app.state.config)

    try:
        return service.ensure_access(payload.mount_path)
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Headphone access check failed: %s", exc)
        return {"ok": False, "message": f"Headphone access check failed: {exc}"}


@router.post("/headphones/transfer")
async def transfer_to_headphones(
    payload: HeadphonesTransferRequest,
    request: Request,
) -> dict[str, Any]:
    """Transfer music to the selected headphones mount path."""

    service = HeadphonesService(request.app.state.config)

    try:
        return service.transfer_to_mount(payload.mount_path, payload.source)
    except ValueError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("Headphone transfer failed: %s", exc)
        return {"ok": False, "message": f"Headphone transfer failed: {exc}"}
