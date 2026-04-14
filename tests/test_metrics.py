# tests/test_metrics.py
"""Tests for Prometheus metrics."""

from pathlib import Path

import pytest

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
from music_ferry.library import Library
from music_ferry.transfer import InteractiveTransfer


def _get_sample_value(metric, sample_name: str, labels: dict[str, str]) -> float:
    for metric_family in metric.collect():
        for sample in metric_family.samples:
            if sample.name != sample_name:
                continue
            if all(sample.labels.get(key) == value for key, value in labels.items()):
                return float(sample.value)
    return 0.0


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
        from music_ferry.metrics.collectors import (
            record_sync_complete,
            sync_duration_seconds,
            sync_last_duration_seconds,
            sync_last_success_timestamp,
            sync_total,
        )

        labels = {"source": "spotify"}
        counter_labels = {**labels, "status": "success"}
        before_total = _get_sample_value(
            sync_total,
            "music_ferry_sync_total",
            counter_labels,
        )
        before_count = _get_sample_value(
            sync_duration_seconds,
            "music_ferry_sync_duration_seconds_count",
            labels,
        )

        record_sync_complete("spotify", success=True, tracks=5, duration_seconds=12.5)

        assert (
            _get_sample_value(sync_total, "music_ferry_sync_total", counter_labels)
            == before_total + 1
        )
        assert (
            _get_sample_value(
                sync_duration_seconds,
                "music_ferry_sync_duration_seconds_count",
                labels,
            )
            == before_count + 1
        )
        assert sync_last_duration_seconds.labels(source="spotify")._value.get() == 12.5
        assert sync_last_success_timestamp.labels(source="spotify")._value.get() > 0

    def test_record_sync_failure(self):
        from music_ferry.metrics.collectors import (
            record_sync_complete,
            sync_last_success_timestamp,
            sync_total,
        )

        before_total = _get_sample_value(
            sync_total,
            "music_ferry_sync_total",
            {"source": "youtube", "status": "failure"},
        )
        before_success_timestamp = sync_last_success_timestamp.labels(
            source="youtube"
        )._value.get()

        record_sync_complete("youtube", success=False, tracks=0)

        assert (
            _get_sample_value(
                sync_total,
                "music_ferry_sync_total",
                {"source": "youtube", "status": "failure"},
            )
            == before_total + 1
        )
        assert (
            sync_last_success_timestamp.labels(source="youtube")._value.get()
            == before_success_timestamp
        )


class TestHeadphonesTransferMetrics:
    def test_transfer_metrics_are_recorded(self, mock_config: Config):
        from music_ferry.metrics.collectors import (
            headphones_transfer_bytes_total,
            headphones_transfer_duration_seconds,
            headphones_transfer_files_total,
            headphones_transfer_last_duration_seconds,
            headphones_transfer_last_success_timestamp,
            headphones_transfer_total,
        )

        spotify_dir = mock_config.paths.music_dir / "spotify"
        music_dir = spotify_dir / "music"
        music_dir.mkdir(parents=True, exist_ok=True)

        mount_music_dir = (
            mock_config.paths.headphones_mount
            / mock_config.paths.headphones_music_folder
        )
        mount_music_dir.mkdir(parents=True, exist_ok=True)

        track_bytes = b"fake mp3 data"
        track_path = music_dir / "track1.mp3"
        track_path.write_bytes(track_bytes)

        library = Library(spotify_dir / "library.json")
        library.add_track(
            track_id="track1",
            filename="track1.mp3",
            title="Track 1",
            artist="Artist 1",
            playlist_id="playlist1",
            size_bytes=len(track_bytes),
        )
        library.update_playlist("playlist1", "Playlist 1", track_count=1)

        transfer = InteractiveTransfer(
            mock_config,
            sources=["spotify"],
            spotify_library=library,
            auto=True,
        )

        labels = {"source": "spotify", "operation": "sync_changes"}
        before_total = _get_sample_value(
            headphones_transfer_total,
            "music_ferry_headphones_transfer_total",
            {**labels, "status": "success"},
        )
        before_count = _get_sample_value(
            headphones_transfer_duration_seconds,
            "music_ferry_headphones_transfer_duration_seconds_count",
            labels,
        )
        before_files = _get_sample_value(
            headphones_transfer_files_total,
            "music_ferry_headphones_transfer_files_total",
            {**labels, "action": "copied"},
        )
        before_bytes = _get_sample_value(
            headphones_transfer_bytes_total,
            "music_ferry_headphones_transfer_bytes_total",
            {**labels, "action": "copied"},
        )

        copied, removed = transfer.sync_changes(auto=True)

        assert copied == 1
        assert removed == 0
        assert (
            _get_sample_value(
                headphones_transfer_total,
                "music_ferry_headphones_transfer_total",
                {**labels, "status": "success"},
            )
            == before_total + 1
        )
        assert (
            _get_sample_value(
                headphones_transfer_duration_seconds,
                "music_ferry_headphones_transfer_duration_seconds_count",
                labels,
            )
            == before_count + 1
        )
        assert (
            _get_sample_value(
                headphones_transfer_files_total,
                "music_ferry_headphones_transfer_files_total",
                {**labels, "action": "copied"},
            )
            == before_files + 1
        )
        assert (
            _get_sample_value(
                headphones_transfer_bytes_total,
                "music_ferry_headphones_transfer_bytes_total",
                {**labels, "action": "copied"},
            )
            == before_bytes + len(track_bytes)
        )
        assert (
            headphones_transfer_last_duration_seconds.labels(
                source="spotify",
                operation="sync_changes",
            )._value.get()
            >= 0
        )
        assert (
            headphones_transfer_last_success_timestamp.labels(
                source="spotify",
                operation="sync_changes",
            )._value.get()
            > 0
        )


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
