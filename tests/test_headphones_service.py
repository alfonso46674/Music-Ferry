"""Unit tests for the headphones service transfer behavior."""

import subprocess
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


def test_describe_mount_autofs_only_is_reported_offline(tmp_path: Path):
    config = _make_config(tmp_path)
    service = HeadphonesService(config)

    mount = config.paths.headphones_mount
    device = service._describe_mount(mount, [("systemd-1", "autofs")])

    assert device["connected"] is False
    assert device["accessible"] is False
    assert device["music_folder_exists"] is False
    assert device["reason"] == "Automount waiting for device"


def test_delete_mp3_files_removes_only_mp3(tmp_path: Path):
    config = _make_config(tmp_path)
    service = HeadphonesService(config)
    service._is_real_mounted = lambda _m: True

    mount = config.paths.headphones_mount
    destination = mount / config.paths.headphones_music_folder
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "one.mp3").write_bytes(b"1")
    (destination / "two.mp3").write_bytes(b"22")
    (destination / "keep.txt").write_text("keep", encoding="utf-8")

    result = service.delete_mp3_files(str(mount))

    assert result["ok"] is True
    assert result["deleted"] == 2
    assert result["bytes_freed"] == 3
    assert not (destination / "one.mp3").exists()
    assert not (destination / "two.mp3").exists()
    assert (destination / "keep.txt").exists()


def test_prepare_unplug_reports_success_when_not_mounted(tmp_path: Path):
    config = _make_config(tmp_path)
    service = HeadphonesService(config)

    result = service.prepare_unplug(str(config.paths.headphones_mount))

    assert result["ok"] is True
    assert result["synced"] is True
    assert result["unmounted"] is True


def test_prepare_unplug_handles_umount_permission_error(
    tmp_path: Path,
    monkeypatch,
):
    config = _make_config(tmp_path)
    service = HeadphonesService(config)
    mount = config.paths.headphones_mount

    monkeypatch.setattr(service, "_is_real_mounted", lambda _m: True)

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=["umount", str(mount)],
            returncode=1,
            stdout="",
            stderr="permission denied",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = service.prepare_unplug(str(mount))

    assert result["ok"] is False
    assert result["synced"] is True
    assert result["unmounted"] is False
    assert "host permissions" in result["message"].lower()


def test_prepare_unplug_uses_helper_when_direct_umount_fails(
    tmp_path: Path,
    monkeypatch,
):
    config = _make_config(tmp_path)
    service = HeadphonesService(config)
    mount = config.paths.headphones_mount

    monkeypatch.setattr(service, "_is_real_mounted", lambda _m: True)

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(
            args=["umount", str(mount)],
            returncode=1,
            stdout="",
            stderr="permission denied",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        service,
        "_try_helper_prepare_unplug",
        lambda _m: {
            "ok": True,
            "synced": True,
            "unmounted": True,
            "message": f"Unmounted {mount} via host helper.",
        },
    )

    result = service.prepare_unplug(str(mount))

    assert result["ok"] is True
    assert result["synced"] is True
    assert result["unmounted"] is True
    assert "host helper" in result["message"].lower()


def test_prepare_unplug_rejects_non_configured_mount(tmp_path: Path):
    config = _make_config(tmp_path)
    service = HeadphonesService(config)

    with pytest.raises(ValueError, match="restricted"):
        service.prepare_unplug(str(tmp_path / "another-device"))
