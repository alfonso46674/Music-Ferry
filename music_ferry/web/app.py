# music_ferry/web/app.py
"""FastAPI application factory for Music Ferry web UI."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from music_ferry import __version__
from music_ferry.config import Config
from music_ferry.web.routes import api, logs, metrics

logger = logging.getLogger(__name__)


def _get_static_path() -> Path | None:
    """Get the path to static files directory."""
    import importlib.resources

    try:
        static_path = importlib.resources.files("music_ferry.web") / "static"
        if static_path.is_dir():  # type: ignore[union-attr]
            return Path(str(static_path))
    except (TypeError, FileNotFoundError):
        pass
    return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown events."""
    logger.info("Music Ferry web UI starting up")
    yield
    logger.info("Music Ferry web UI shutting down")


def create_app(config: Config) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Music Ferry configuration object.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="Music Ferry",
        description="Web UI for Music Ferry - ferry music from Spotify and YouTube",
        version=__version__,
        lifespan=lifespan,
    )

    # Store config in app state for access in routes
    app.state.config = config

    # Include API routes
    app.include_router(api.router, prefix="/api/v1", tags=["api"])
    app.include_router(logs.router, prefix="/api/v1", tags=["logs"])
    app.include_router(metrics.router, tags=["metrics"])

    # Get static files path
    static_path = _get_static_path()

    if static_path:
        # Serve index.html at root
        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            return FileResponse(static_path / "index.html")

        # Mount static files
        app.mount(
            "/static",
            StaticFiles(directory=str(static_path)),
            name="static",
        )
    else:
        logger.debug("Static files directory not found, skipping mount")

        @app.get("/", include_in_schema=False)
        async def serve_placeholder() -> dict[str, str]:
            return {"message": "Music Ferry API", "docs": "/docs"}

    return app
