# music_ferry/web/routes/metrics.py
"""Prometheus metrics endpoint."""

import logging

from fastapi import APIRouter, Request, Response

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/metrics")
async def get_metrics(request: Request) -> Response:
    """Expose Prometheus metrics."""
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    from music_ferry.metrics.collectors import update_library_metrics

    # Update library metrics before generating output
    config = request.app.state.config
    update_library_metrics(config)

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
