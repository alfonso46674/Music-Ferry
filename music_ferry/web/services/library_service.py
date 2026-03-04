# music_ferry/web/services/library_service.py
"""Service for reading and summarizing library data."""

import logging
from typing import Any

from music_ferry.config import Config
from music_ferry.library import Library

logger = logging.getLogger(__name__)


class LibraryService:
    """Service for accessing library data from JSON files."""

    def __init__(self, config: Config):
        self.config = config
        self._spotify_library: Library | None = None
        self._youtube_library: Library | None = None

    @property
    def spotify_library(self) -> Library | None:
        """Lazily load Spotify library."""
        if self._spotify_library is None:
            path = self.config.paths.music_dir / "spotify" / "library.json"
            if path.exists():
                self._spotify_library = Library(path)
        return self._spotify_library

    @property
    def youtube_library(self) -> Library | None:
        """Lazily load YouTube library."""
        if self._youtube_library is None:
            path = self.config.paths.music_dir / "youtube" / "library.json"
            if path.exists():
                self._youtube_library = Library(path)
        return self._youtube_library

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all libraries."""
        spotify_summary = self._get_source_summary("spotify", self.spotify_library)
        youtube_summary = self._get_source_summary("youtube", self.youtube_library)

        return {
            "spotify": spotify_summary,
            "youtube": youtube_summary,
            "total": {
                "tracks": spotify_summary["tracks"] + youtube_summary["tracks"],
                "playlists": spotify_summary["playlists"]
                + youtube_summary["playlists"],
                "size_bytes": spotify_summary["size_bytes"]
                + youtube_summary["size_bytes"],
            },
        }

    def _get_source_summary(
        self, source: str, library: Library | None
    ) -> dict[str, Any]:
        """Get summary for a single source."""
        if library is None:
            return {
                "tracks": 0,
                "playlists": 0,
                "size_bytes": 0,
                "enabled": (
                    getattr(self.config, source).enabled
                    if hasattr(self.config, source)
                    else False
                ),
            }

        tracks = library.get_all_tracks()
        playlists = library.get_all_playlists()
        total_size = sum(t.size_bytes or 0 for t in tracks)

        config_section = getattr(self.config, source, None)
        enabled = config_section.enabled if config_section else False

        return {
            "tracks": len(tracks),
            "playlists": len(playlists),
            "size_bytes": total_size,
            "enabled": enabled,
        }

    def get_detail(self, source: str) -> dict[str, Any]:
        """Get detailed library info for a specific source."""
        if source == "spotify":
            library = self.spotify_library
        elif source == "youtube":
            library = self.youtube_library
        else:
            return {"error": f"Unknown source: {source}"}

        if library is None:
            return {
                "source": source,
                "tracks": [],
                "playlists": [],
                "error": "Library not found",
            }

        tracks = library.get_all_tracks()
        playlists = library.get_all_playlists()

        return {
            "source": source,
            "tracks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "artist": t.artist,
                    "filename": t.filename,
                    "size_bytes": t.size_bytes,
                    "playlists": t.playlists,
                    "is_orphaned": t.is_orphaned,
                }
                for t in tracks
            ],
            "playlists": [
                {
                    "id": p.id,
                    "name": p.name,
                    "last_synced": p.last_synced,
                    "track_count": p.track_count,
                }
                for p in playlists
            ],
        }

    def get_sanitized_config(self) -> dict[str, Any]:
        """Get configuration with secrets redacted."""
        return {
            "spotify": {
                "enabled": self.config.spotify.enabled,
                "client_id": _redact(self.config.spotify.client_id),
                "client_secret": _redact(self.config.spotify.client_secret),
                "username": self.config.spotify.username,
                "playlists": [
                    {"name": p.name, "url": p.url, "max_gb": p.max_gb}
                    for p in self.config.spotify.playlists
                ],
            },
            "youtube": {
                "enabled": self.config.youtube.enabled,
                "retry_count": self.config.youtube.retry_count,
                "retry_delay_seconds": self.config.youtube.retry_delay_seconds,
                "playlists": [
                    {"name": p.name, "url": p.url, "max_gb": p.max_gb}
                    for p in self.config.youtube.playlists
                ],
            },
            "audio": {
                "bitrate": self.config.audio.bitrate,
                "format": self.config.audio.format,
            },
            "paths": {
                "music_dir": str(self.config.paths.music_dir),
                "headphones_mount": str(self.config.paths.headphones_mount),
                "headphones_music_folder": self.config.paths.headphones_music_folder,
            },
            "notifications": {
                "ntfy_topic": _redact(self.config.notifications.ntfy_topic),
                "ntfy_server": self.config.notifications.ntfy_server,
                "notify_on_success": self.config.notifications.notify_on_success,
                "notify_on_failure": self.config.notifications.notify_on_failure,
            },
            "behavior": {
                "skip_existing": self.config.behavior.skip_existing,
                "trim_silence": self.config.behavior.trim_silence,
            },
            "transfer": {
                "reserve_free_gb": self.config.transfer.reserve_free_gb,
            },
        }


def _redact(value: str, visible_chars: int = 4) -> str:
    """Redact a secret value, showing only first few characters."""
    if not value or len(value) <= visible_chars:
        return "****"
    return value[:visible_chars] + "****"
