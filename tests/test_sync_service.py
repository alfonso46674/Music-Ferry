"""Tests for web sync scheduling service."""

from pathlib import Path

from fastapi import FastAPI

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
from music_ferry.web.services.sync_service import SyncService


def make_config(tmp_path: Path) -> Config:
    """Build test config with isolated data directory."""
    return Config(
        spotify=SpotifyConfig(
            client_id="id",
            client_secret="secret",
            username="user",
            enabled=False,
            playlists=[],
        ),
        youtube=YouTubeConfig(enabled=True, playlists=[]),
        audio=AudioConfig(bitrate=192, format="mp3"),
        paths=PathsConfig(
            music_dir=tmp_path / ".music-ferry",
            headphones_mount=tmp_path / "headphones",
        ),
        notifications=NotificationsConfig(ntfy_topic="topic"),
        behavior=BehaviorConfig(),
        transfer=TransferConfig(),
    )


def make_service(tmp_path: Path) -> SyncService:
    """Create SyncService bound to a FastAPI app for tests."""
    app = FastAPI()
    app.state.config = make_config(tmp_path)
    return SyncService(app)


class TestSyncServiceSchedule:
    def test_schedule_defaults(self, tmp_path: Path):
        service = make_service(tmp_path)

        schedule = service.get_schedule()
        assert schedule["enabled"] is False
        assert schedule["time"] == "05:00"
        assert schedule["source"] == "youtube"
        assert schedule["next_run"] is None

    def test_schedule_update_persists_to_disk(self, tmp_path: Path):
        service = make_service(tmp_path)

        updated = service.update_schedule(
            enabled=True,
            time="06:45",
            source="all",
        )
        assert updated["enabled"] is True
        assert updated["time"] == "06:45"
        assert updated["source"] == "all"
        assert updated["next_run"] is not None

        # Re-create service to verify persistence is loaded from disk.
        reloaded = make_service(tmp_path)
        schedule = reloaded.get_schedule()
        assert schedule["enabled"] is True
        assert schedule["time"] == "06:45"
        assert schedule["source"] == "all"

    def test_schedule_invalid_time_raises(self, tmp_path: Path):
        service = make_service(tmp_path)

        try:
            service.update_schedule(
                enabled=True,
                time="27:99",
                source="youtube",
            )
        except ValueError as exc:
            assert "Time must be between 00:00 and 23:59." in str(exc)
        else:  # pragma: no cover - explicit assertion path
            raise AssertionError("Expected ValueError for invalid schedule time")

    def test_schedule_invalid_source_raises(self, tmp_path: Path):
        service = make_service(tmp_path)

        try:
            service.update_schedule(
                enabled=True,
                time="06:00",
                source="invalid",
            )
        except ValueError as exc:
            assert "Source must be one of: all, spotify, youtube." in str(exc)
        else:  # pragma: no cover - explicit assertion path
            raise AssertionError("Expected ValueError for invalid schedule source")
