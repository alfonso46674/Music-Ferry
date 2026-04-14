# music_ferry/metrics/collectors.py
"""Custom Prometheus collectors for Music Ferry."""

import logging
import time

from prometheus_client import Counter, Gauge, Histogram

from music_ferry.config import Config
from music_ferry.library import Library

logger = logging.getLogger(__name__)

# Library metrics (gauges - updated on scrape)
tracks_total = Gauge(
    "music_ferry_tracks_total",
    "Total number of tracks in library",
    ["source"],
)

playlists_total = Gauge(
    "music_ferry_playlists_total",
    "Total number of playlists in library",
    ["source"],
)

library_size_bytes = Gauge(
    "music_ferry_library_size_bytes",
    "Total size of library in bytes",
    ["source"],
)

# Sync metrics (counters/histograms - updated during operations)
sync_total = Counter(
    "music_ferry_sync_total",
    "Total number of sync operations",
    ["source", "status"],
)

sync_duration_seconds = Histogram(
    "music_ferry_sync_duration_seconds",
    "Duration of sync operations in seconds",
    ["source"],
    buckets=(30, 60, 120, 300, 600, 1200, 3600),
)

sync_last_duration_seconds = Gauge(
    "music_ferry_sync_last_duration_seconds",
    "Duration in seconds of the most recent sync operation",
    ["source"],
)

tracks_downloaded_total = Counter(
    "music_ferry_tracks_downloaded_total",
    "Total number of tracks downloaded",
    ["source"],
)

sync_last_success_timestamp = Gauge(
    "music_ferry_sync_last_success_timestamp",
    "Unix timestamp of last successful sync",
    ["source"],
)

headphones_transfer_total = Counter(
    "music_ferry_headphones_transfer_total",
    "Total number of headphone transfer operations",
    ["source", "operation", "status"],
)

headphones_transfer_duration_seconds = Histogram(
    "music_ferry_headphones_transfer_duration_seconds",
    "Duration of headphone transfer operations in seconds",
    ["source", "operation"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1200),
)

headphones_transfer_last_duration_seconds = Gauge(
    "music_ferry_headphones_transfer_last_duration_seconds",
    "Duration in seconds of the most recent headphone transfer operation",
    ["source", "operation"],
)

headphones_transfer_last_success_timestamp = Gauge(
    "music_ferry_headphones_transfer_last_success_timestamp",
    "Unix timestamp of the last successful headphone transfer",
    ["source", "operation"],
)

headphones_transfer_files_total = Counter(
    "music_ferry_headphones_transfer_files_total",
    "Total number of files copied to or removed from headphones",
    ["source", "operation", "action"],
)

headphones_transfer_bytes_total = Counter(
    "music_ferry_headphones_transfer_bytes_total",
    "Total number of bytes copied to or removed from headphones",
    ["source", "operation", "action"],
)


def update_library_metrics(config: Config) -> None:
    """Update library metrics by reading current library state.

    This is called before each /metrics scrape to ensure fresh data.
    """
    # Update Spotify metrics
    spotify_path = config.paths.music_dir / "spotify" / "library.json"
    if spotify_path.exists():
        try:
            library = Library(spotify_path)
            tracks = library.get_all_tracks()
            playlists = library.get_all_playlists()

            tracks_total.labels(source="spotify").set(len(tracks))
            playlists_total.labels(source="spotify").set(len(playlists))
            library_size_bytes.labels(source="spotify").set(
                sum(t.size_bytes or 0 for t in tracks)
            )
        except Exception as e:
            logger.warning(f"Failed to read Spotify library for metrics: {e}")
    else:
        tracks_total.labels(source="spotify").set(0)
        playlists_total.labels(source="spotify").set(0)
        library_size_bytes.labels(source="spotify").set(0)

    # Update YouTube metrics
    youtube_path = config.paths.music_dir / "youtube" / "library.json"
    if youtube_path.exists():
        try:
            library = Library(youtube_path)
            tracks = library.get_all_tracks()
            playlists = library.get_all_playlists()

            tracks_total.labels(source="youtube").set(len(tracks))
            playlists_total.labels(source="youtube").set(len(playlists))
            library_size_bytes.labels(source="youtube").set(
                sum(t.size_bytes or 0 for t in tracks)
            )
        except Exception as e:
            logger.warning(f"Failed to read YouTube library for metrics: {e}")
    else:
        tracks_total.labels(source="youtube").set(0)
        playlists_total.labels(source="youtube").set(0)
        library_size_bytes.labels(source="youtube").set(0)


def record_sync_start(source: str) -> None:
    """Record the start of a sync operation."""
    pass  # Timer is handled by decorator


def record_sync_complete(
    source: str,
    success: bool,
    tracks: int,
    duration_seconds: float | None = None,
) -> None:
    """Record completion of a sync operation."""
    status = "success" if success else "failure"
    sync_total.labels(source=source, status=status).inc()

    if duration_seconds is not None:
        sync_duration_seconds.labels(source=source).observe(duration_seconds)
        sync_last_duration_seconds.labels(source=source).set(duration_seconds)

    if success:
        sync_last_success_timestamp.labels(source=source).set(time.time())

    if tracks > 0:
        tracks_downloaded_total.labels(source=source).inc(tracks)


def record_headphones_transfer(
    source: str,
    operation: str,
    status: str,
    files_copied: int,
    files_removed: int,
    bytes_copied: int,
    bytes_removed: int,
    duration_seconds: float,
) -> None:
    """Record completion of a headphone transfer operation."""
    headphones_transfer_total.labels(
        source=source,
        operation=operation,
        status=status,
    ).inc()
    headphones_transfer_duration_seconds.labels(
        source=source,
        operation=operation,
    ).observe(duration_seconds)
    headphones_transfer_last_duration_seconds.labels(
        source=source,
        operation=operation,
    ).set(duration_seconds)

    if status == "success":
        headphones_transfer_last_success_timestamp.labels(
            source=source,
            operation=operation,
        ).set(time.time())

    if files_copied > 0:
        headphones_transfer_files_total.labels(
            source=source,
            operation=operation,
            action="copied",
        ).inc(files_copied)
    if files_removed > 0:
        headphones_transfer_files_total.labels(
            source=source,
            operation=operation,
            action="removed",
        ).inc(files_removed)
    if bytes_copied > 0:
        headphones_transfer_bytes_total.labels(
            source=source,
            operation=operation,
            action="copied",
        ).inc(bytes_copied)
    if bytes_removed > 0:
        headphones_transfer_bytes_total.labels(
            source=source,
            operation=operation,
            action="removed",
        ).inc(bytes_removed)
