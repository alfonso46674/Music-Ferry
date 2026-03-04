# tests/test_metrics.py
"""Tests for Prometheus metrics."""

import pytest
from pathlib import Path

from music_ferry.config import (
    AudioConfig,
    BehaviorConfig,
    Config,
    NotificationsConfig,
    PathsConfig,
    SpotifyConfig,
    TransferConfig,
    YouTubeConfig,
)


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create a mock configuration for testing."""
    return Config(
        spotify=SpotifyConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            username="test_user",
            enabled=True,
            playlists=[],
        ),
        youtube=YouTubeConfig(
            enabled=False,
            playlists=[],
        ),
        audio=AudioConfig(bitrate=192, format="mp3"),
        paths=PathsConfig(
            music_dir=tmp_path / ".music-ferry",
            headphones_mount=tmp_path / "headphones",
        ),
        notifications=NotificationsConfig(
            ntfy_topic="test-topic",
        ),
        behavior=BehaviorConfig(),
        transfer=TransferConfig(),
    )


class TestLibraryMetrics:
    def test_update_library_metrics_no_libraries(self, mock_config: Config):
        from music_ferry.metrics.collectors import update_library_metrics

        # Should not raise when libraries don't exist
        update_library_metrics(mock_config)

    def test_update_library_metrics_with_library(self, mock_config: Config):
        from music_ferry.library import Library
        from music_ferry.metrics.collectors import (
            library_size_bytes,
            playlists_total,
            tracks_total,
            update_library_metrics,
        )

        # Create a library with some data
        spotify_dir = mock_config.paths.music_dir / "spotify"
        spotify_dir.mkdir(parents=True, exist_ok=True)

        library = Library(spotify_dir / "library.json")
        library.add_track(
            track_id="track1",
            filename="track1.mp3",
            title="Test Track",
            artist="Test Artist",
            playlist_id="playlist1",
            size_bytes=1024000,
        )
        library.update_playlist("playlist1", "Test Playlist", track_count=1)

        # Update metrics
        update_library_metrics(mock_config)

        # Check metrics values
        assert tracks_total.labels(source="spotify")._value.get() == 1
        assert playlists_total.labels(source="spotify")._value.get() == 1
        assert library_size_bytes.labels(source="spotify")._value.get() == 1024000


class TestSyncMetrics:
    def test_record_sync_complete(self):
        from music_ferry.metrics.collectors import record_sync_complete, sync_total

        # Record a successful sync
        record_sync_complete("spotify", success=True, tracks=5)

        # Check counter was incremented
        assert sync_total.labels(source="spotify", status="success")._value.get() >= 1

    def test_record_sync_failure(self):
        from music_ferry.metrics.collectors import record_sync_complete, sync_total

        # Record a failed sync
        record_sync_complete("youtube", success=False, tracks=0)

        # Check counter was incremented
        assert sync_total.labels(source="youtube", status="failure")._value.get() >= 1


class TestTimedDecorator:
    @pytest.mark.asyncio
    async def test_timed_sync_async(self):
        from music_ferry.metrics.decorators import timed_sync

        @timed_sync("test_source")
        async def sample_async_function():
            return "done"

        result = await sample_async_function()
        assert result == "done"

    def test_timed_sync_sync(self):
        from music_ferry.metrics.decorators import timed_sync

        @timed_sync("test_source")
        def sample_sync_function():
            return "done"

        result = sample_sync_function()
        assert result == "done"
