# music_ferry/web/routes/logs.py
"""Log streaming endpoint using Server-Sent Events."""

import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()
logger = logging.getLogger(__name__)


async def log_generator(request: Request) -> AsyncGenerator[dict[str, str], None]:
    """Generate log events for SSE streaming."""
    from music_ferry.web.services.log_service import LogService

    config = request.app.state.config
    log_service = LogService(config)

    async for line in log_service.tail_logs():
        # Check if client disconnected
        if await request.is_disconnected():
            break
        yield {"event": "log", "data": line}


@router.get("/logs/stream")
async def stream_logs(request: Request) -> EventSourceResponse:
    """Stream log lines via Server-Sent Events."""
    return EventSourceResponse(log_generator(request))
