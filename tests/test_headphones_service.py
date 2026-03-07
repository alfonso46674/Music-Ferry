"""Unit tests for the headphones service transfer behavior."""

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
from music_ferry.library import Library
from music_ferry.web.services.headphones_service import HeadphonesService


def _make_config(tmp_path: Path) -> Config:
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
        notifications=NotificationsConfig(ntfy_topic="test-topic"),
        behavior=BehaviorConfig(),
        transfer=TransferConfig(),
    )


def _seed_spotify_track(config: Config) -> None:
    spotify_dir = config.paths.music_dir / "spotify"
    spotify_music = spotify_dir / "music"
    spotify_music.mkdir(parents=True, exist_ok=True)

    library = Library(spotify_dir / "library.json")
    library.add_track(
        "track1",
        "track1.mp3",
        "Track One",
        "Artist One",
        "playlist1",
        size_bytes=4,
    )
    library.update_playlist("playlist1", "Playlist One", 1, track_order=["track1"])
    (spotify_music / "track1.mp3").write_bytes(b"data")


def test_transfer_reports_already_synced(tmp_path: Path):
    config = _make_config(tmp_path)
    _seed_spotify_track(config)

    mount = config.paths.headphones_mount
    destination = mount / config.paths.headphones_music_folder
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "track1.mp3").write_bytes(b"data")

    service = HeadphonesService(config)
    result = service.transfer_to_mount(str(mount), source="spotify")

    assert result["ok"] is True
    assert result["copied"] == 0
    assert result["removed"] == 0
    assert "already up to date" in result["message"].lower()
    assert result["before"]["new_to_transfer"] == 0
    assert result["status"]["new_to_transfer"] == 0


def test_transfer_includes_before_after_status(tmp_path: Path):
    config = _make_config(tmp_path)
    _seed_spotify_track(config)

    mount = config.paths.headphones_mount
    destination = mount / config.paths.headphones_music_folder
    destination.mkdir(parents=True, exist_ok=True)

    service = HeadphonesService(config)
    result = service.transfer_to_mount(str(mount), source="spotify")

    assert result["ok"] is True
    assert result["copied"] == 1
    assert result["removed"] == 0
    assert result["before"]["new_to_transfer"] == 1
    assert result["status"]["new_to_transfer"] == 0
