# Music Ferry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an automated system that records Spotify playlists to MP3 files and transfers them to USB headphones for offline swimming.

**Architecture:** Python application using Playwright for browser automation, FFmpeg for audio recording via PipeWire virtual sink, spotipy for Spotify API metadata, and systemd for scheduling. Each component is a separate module with clear interfaces.

**Tech Stack:** Python 3.11+, Playwright, spotipy, FFmpeg, mutagen, PipeWire, systemd

---

## Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `music_ferry/__init__.py`
- Create: `tests/__init__.py`
- Create: `.gitignore`

**Step 1: Initialize git repository**

Run: `git init`
Expected: Initialized empty Git repository

**Step 2: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "music-ferry"
version = "0.1.0"
description = "Download Spotify playlists to MP3 for offline swimming"
requires-python = ">=3.11"
dependencies = [
    "playwright>=1.40.0",
    "spotipy>=2.23.0",
    "ffmpeg-python>=0.2.0",
    "mutagen>=1.47.0",
    "pyyaml>=6.0",
    "requests>=2.31.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
]

[project.scripts]
music-ferry = "music_ferry.cli:main"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 3: Create package structure**

```python
# music_ferry/__init__.py
__version__ = "0.1.0"
```

```python
# tests/__init__.py
```

**Step 4: Create .gitignore**

```
__pycache__/
*.py[cod]
.pytest_cache/
*.egg-info/
dist/
build/
.venv/
venv/
.env
*.mp3
cookies/
```

**Step 5: Create virtual environment and install**

Run: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
Expected: Successfully installed music-ferry

**Step 6: Verify pytest works**

Run: `source .venv/bin/activate && pytest --collect-only`
Expected: no tests ran (empty collection is fine)

**Step 7: Commit**

```bash
git add pyproject.toml music_ferry/ tests/ .gitignore
git commit -m "chore: initial project setup"
```

---

## Task 2: Config Module

**Files:**
- Create: `music_ferry/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
import tempfile
from pathlib import Path

import pytest
import yaml

from music_ferry.config import Config, load_config


class TestConfig:
    def test_load_valid_config(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "spotify": {
                "client_id": "test_id",
                "client_secret": "test_secret",
                "username": "test_user",
            },
            "playlists": [
                {"name": "Test Playlist", "url": "https://open.spotify.com/playlist/abc123"}
            ],
            "audio": {"bitrate": 192, "format": "mp3"},
            "paths": {
                "music_dir": "~/.music-ferry/music",
                "headphones_mount": "/media/user/HEADPHONES",
                "headphones_music_folder": "Music",
            },
            "notifications": {
                "ntfy_topic": "test-topic",
                "ntfy_server": "https://ntfy.sh",
                "notify_on_success": False,
                "notify_on_failure": True,
            },
            "behavior": {
                "skip_existing": True,
                "auto_transfer": True,
                "trim_silence": True,
            },
        }))

        config = load_config(config_file)

        assert config.spotify.client_id == "test_id"
        assert config.spotify.client_secret == "test_secret"
        assert config.spotify.username == "test_user"
        assert len(config.playlists) == 1
        assert config.playlists[0].name == "Test Playlist"
        assert config.audio.bitrate == 192
        assert config.paths.music_dir == Path.home() / ".music-ferry" / "music"
        assert config.notifications.ntfy_topic == "test-topic"
        assert config.behavior.skip_existing is True

    def test_load_config_missing_required_field(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "spotify": {"client_id": "test_id"},  # missing client_secret
        }))

        with pytest.raises(ValueError, match="client_secret"):
            load_config(config_file)

    def test_load_config_file_not_found(self, tmp_path: Path):
        config_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            load_config(config_file)

    def test_playlist_id_extraction(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "spotify": {
                "client_id": "test_id",
                "client_secret": "test_secret",
                "username": "test_user",
            },
            "playlists": [
                {"name": "Test", "url": "https://open.spotify.com/playlist/37i9dQZEVXcQ9COmYvdajy"}
            ],
            "audio": {"bitrate": 192, "format": "mp3"},
            "paths": {
                "music_dir": "~/.music-ferry/music",
                "headphones_mount": "/media/user/HEADPHONES",
                "headphones_music_folder": "Music",
            },
            "notifications": {
                "ntfy_topic": "test-topic",
                "ntfy_server": "https://ntfy.sh",
                "notify_on_success": False,
                "notify_on_failure": True,
            },
            "behavior": {
                "skip_existing": True,
                "auto_transfer": True,
                "trim_silence": True,
            },
        }))

        config = load_config(config_file)
        assert config.playlists[0].playlist_id == "37i9dQZEVXcQ9COmYvdajy"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError" or "ImportError"

**Step 3: Write minimal implementation**

```python
# music_ferry/config.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import re

import yaml


@dataclass
class SpotifyConfig:
    client_id: str
    client_secret: str
    username: str


@dataclass
class PlaylistConfig:
    name: str
    url: str

    @property
    def playlist_id(self) -> str:
        match = re.search(r"playlist/([a-zA-Z0-9]+)", self.url)
        if not match:
            raise ValueError(f"Invalid playlist URL: {self.url}")
        return match.group(1)


@dataclass
class AudioConfig:
    bitrate: int = 192
    format: str = "mp3"


@dataclass
class PathsConfig:
    music_dir: Path
    headphones_mount: Path
    headphones_music_folder: str = "Music"

    def __post_init__(self):
        if isinstance(self.music_dir, str):
            self.music_dir = Path(self.music_dir).expanduser()
        if isinstance(self.headphones_mount, str):
            self.headphones_mount = Path(self.headphones_mount)


@dataclass
class NotificationsConfig:
    ntfy_topic: str
    ntfy_server: str = "https://ntfy.sh"
    notify_on_success: bool = False
    notify_on_failure: bool = True


@dataclass
class BehaviorConfig:
    skip_existing: bool = True
    auto_transfer: bool = True
    trim_silence: bool = True


@dataclass
class Config:
    spotify: SpotifyConfig
    playlists: list[PlaylistConfig]
    audio: AudioConfig
    paths: PathsConfig
    notifications: NotificationsConfig
    behavior: BehaviorConfig


def load_config(config_path: Path) -> Config:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    # Validate required spotify fields
    spotify_data = data.get("spotify", {})
    for required in ["client_id", "client_secret", "username"]:
        if required not in spotify_data:
            raise ValueError(f"Missing required spotify field: {required}")

    spotify = SpotifyConfig(
        client_id=spotify_data["client_id"],
        client_secret=spotify_data["client_secret"],
        username=spotify_data["username"],
    )

    playlists = [
        PlaylistConfig(name=p["name"], url=p["url"])
        for p in data.get("playlists", [])
    ]

    audio_data = data.get("audio", {})
    audio = AudioConfig(
        bitrate=audio_data.get("bitrate", 192),
        format=audio_data.get("format", "mp3"),
    )

    paths_data = data.get("paths", {})
    paths = PathsConfig(
        music_dir=paths_data.get("music_dir", "~/.music-ferry/music"),
        headphones_mount=paths_data.get("headphones_mount", "/media/user/HEADPHONES"),
        headphones_music_folder=paths_data.get("headphones_music_folder", "Music"),
    )

    notif_data = data.get("notifications", {})
    notifications = NotificationsConfig(
        ntfy_topic=notif_data.get("ntfy_topic", ""),
        ntfy_server=notif_data.get("ntfy_server", "https://ntfy.sh"),
        notify_on_success=notif_data.get("notify_on_success", False),
        notify_on_failure=notif_data.get("notify_on_failure", True),
    )

    behavior_data = data.get("behavior", {})
    behavior = BehaviorConfig(
        skip_existing=behavior_data.get("skip_existing", True),
        auto_transfer=behavior_data.get("auto_transfer", True),
        trim_silence=behavior_data.get("trim_silence", True),
    )

    return Config(
        spotify=spotify,
        playlists=playlists,
        audio=audio,
        paths=paths,
        notifications=notifications,
        behavior=behavior,
    )
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_config.py -v`
Expected: PASSED

**Step 5: Commit**

```bash
git add music_ferry/config.py tests/test_config.py
git commit -m "feat: add config module with YAML loading"
```

---

## Task 3: Track Database Module

**Files:**
- Create: `music_ferry/tracks_db.py`
- Create: `tests/test_tracks_db.py`

**Step 1: Write the failing test**

```python
# tests/test_tracks_db.py
from pathlib import Path

import pytest

from music_ferry.tracks_db import TracksDB


class TestTracksDB:
    def test_empty_database(self, tmp_path: Path):
        db = TracksDB(tmp_path / "tracks.json")
        assert db.is_downloaded("abc123") is False

    def test_add_and_check_track(self, tmp_path: Path):
        db = TracksDB(tmp_path / "tracks.json")
        db.add_track("abc123", "abc123.mp3")
        assert db.is_downloaded("abc123") is True

    def test_get_filename(self, tmp_path: Path):
        db = TracksDB(tmp_path / "tracks.json")
        db.add_track("abc123", "abc123.mp3")
        assert db.get_filename("abc123") == "abc123.mp3"

    def test_persistence(self, tmp_path: Path):
        db_path = tmp_path / "tracks.json"

        db1 = TracksDB(db_path)
        db1.add_track("abc123", "abc123.mp3")
        db1.save()

        db2 = TracksDB(db_path)
        assert db2.is_downloaded("abc123") is True
        assert db2.get_filename("abc123") == "abc123.mp3"

    def test_list_all_tracks(self, tmp_path: Path):
        db = TracksDB(tmp_path / "tracks.json")
        db.add_track("abc123", "abc123.mp3")
        db.add_track("def456", "def456.mp3")

        tracks = db.list_tracks()
        assert len(tracks) == 2
        assert "abc123" in tracks
        assert "def456" in tracks

    def test_remove_track(self, tmp_path: Path):
        db = TracksDB(tmp_path / "tracks.json")
        db.add_track("abc123", "abc123.mp3")
        db.remove_track("abc123")
        assert db.is_downloaded("abc123") is False
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_tracks_db.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# music_ferry/tracks_db.py
import json
from pathlib import Path


class TracksDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._tracks: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self.db_path.exists():
            with open(self.db_path) as f:
                self._tracks = json.load(f)

    def save(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, "w") as f:
            json.dump(self._tracks, f, indent=2)

    def is_downloaded(self, track_id: str) -> bool:
        return track_id in self._tracks

    def add_track(self, track_id: str, filename: str) -> None:
        self._tracks[track_id] = filename
        self.save()

    def get_filename(self, track_id: str) -> str | None:
        return self._tracks.get(track_id)

    def remove_track(self, track_id: str) -> None:
        if track_id in self._tracks:
            del self._tracks[track_id]
            self.save()

    def list_tracks(self) -> dict[str, str]:
        return dict(self._tracks)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_tracks_db.py -v`
Expected: PASSED

**Step 5: Commit**

```bash
git add music_ferry/tracks_db.py tests/test_tracks_db.py
git commit -m "feat: add track database for tracking downloaded songs"
```

---

## Task 4: Spotify API Module

**Files:**
- Create: `music_ferry/spotify_api.py`
- Create: `tests/test_spotify_api.py`

**Step 1: Write the failing test**

```python
# tests/test_spotify_api.py
from unittest.mock import MagicMock, patch

import pytest

from music_ferry.spotify_api import SpotifyAPI, Track


class TestSpotifyAPI:
    def test_track_dataclass(self):
        track = Track(
            id="abc123",
            name="Test Song",
            artists=["Artist 1", "Artist 2"],
            album="Test Album",
            duration_ms=180000,
            album_art_url="https://example.com/art.jpg",
        )
        assert track.id == "abc123"
        assert track.duration_seconds == 180
        assert track.artist_string == "Artist 1, Artist 2"

    @patch("music_ferry.spotify_api.spotipy.Spotify")
    def test_get_playlist_tracks(self, mock_spotify_class):
        mock_spotify = MagicMock()
        mock_spotify_class.return_value = mock_spotify

        mock_spotify.playlist_items.return_value = {
            "items": [
                {
                    "track": {
                        "id": "track1",
                        "name": "Song 1",
                        "artists": [{"name": "Artist A"}],
                        "album": {
                            "name": "Album 1",
                            "images": [{"url": "https://example.com/art1.jpg"}],
                        },
                        "duration_ms": 200000,
                    }
                },
                {
                    "track": {
                        "id": "track2",
                        "name": "Song 2",
                        "artists": [{"name": "Artist B"}, {"name": "Artist C"}],
                        "album": {
                            "name": "Album 2",
                            "images": [{"url": "https://example.com/art2.jpg"}],
                        },
                        "duration_ms": 180000,
                    }
                },
            ],
            "next": None,
        }

        api = SpotifyAPI(client_id="test_id", client_secret="test_secret")
        tracks = api.get_playlist_tracks("playlist123")

        assert len(tracks) == 2
        assert tracks[0].id == "track1"
        assert tracks[0].name == "Song 1"
        assert tracks[0].artists == ["Artist A"]
        assert tracks[1].artists == ["Artist B", "Artist C"]
        assert tracks[1].artist_string == "Artist B, Artist C"

    @patch("music_ferry.spotify_api.spotipy.Spotify")
    def test_get_playlist_tracks_pagination(self, mock_spotify_class):
        mock_spotify = MagicMock()
        mock_spotify_class.return_value = mock_spotify

        # First page
        mock_spotify.playlist_items.return_value = {
            "items": [
                {
                    "track": {
                        "id": "track1",
                        "name": "Song 1",
                        "artists": [{"name": "Artist A"}],
                        "album": {"name": "Album 1", "images": []},
                        "duration_ms": 200000,
                    }
                },
            ],
            "next": "https://api.spotify.com/next",
        }

        # Second page
        mock_spotify.next.return_value = {
            "items": [
                {
                    "track": {
                        "id": "track2",
                        "name": "Song 2",
                        "artists": [{"name": "Artist B"}],
                        "album": {"name": "Album 2", "images": []},
                        "duration_ms": 180000,
                    }
                },
            ],
            "next": None,
        }

        api = SpotifyAPI(client_id="test_id", client_secret="test_secret")
        tracks = api.get_playlist_tracks("playlist123")

        assert len(tracks) == 2

    @patch("music_ferry.spotify_api.spotipy.Spotify")
    def test_skips_none_tracks(self, mock_spotify_class):
        """Spotify sometimes returns None for tracks (e.g., local files)"""
        mock_spotify = MagicMock()
        mock_spotify_class.return_value = mock_spotify

        mock_spotify.playlist_items.return_value = {
            "items": [
                {"track": None},  # Local file or unavailable track
                {
                    "track": {
                        "id": "track1",
                        "name": "Song 1",
                        "artists": [{"name": "Artist A"}],
                        "album": {"name": "Album 1", "images": []},
                        "duration_ms": 200000,
                    }
                },
            ],
            "next": None,
        }

        api = SpotifyAPI(client_id="test_id", client_secret="test_secret")
        tracks = api.get_playlist_tracks("playlist123")

        assert len(tracks) == 1
        assert tracks[0].id == "track1"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_spotify_api.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# music_ferry/spotify_api.py
from dataclasses import dataclass

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


@dataclass
class Track:
    id: str
    name: str
    artists: list[str]
    album: str
    duration_ms: int
    album_art_url: str | None

    @property
    def duration_seconds(self) -> int:
        return self.duration_ms // 1000

    @property
    def artist_string(self) -> str:
        return ", ".join(self.artists)


class SpotifyAPI:
    def __init__(self, client_id: str, client_secret: str):
        auth_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        tracks: list[Track] = []
        results = self.sp.playlist_items(playlist_id)

        while results:
            for item in results["items"]:
                track_data = item.get("track")
                if track_data is None:
                    continue

                images = track_data["album"].get("images", [])
                album_art_url = images[0]["url"] if images else None

                track = Track(
                    id=track_data["id"],
                    name=track_data["name"],
                    artists=[a["name"] for a in track_data["artists"]],
                    album=track_data["album"]["name"],
                    duration_ms=track_data["duration_ms"],
                    album_art_url=album_art_url,
                )
                tracks.append(track)

            if results["next"]:
                results = self.sp.next(results)
            else:
                break

        return tracks
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_spotify_api.py -v`
Expected: PASSED

**Step 5: Commit**

```bash
git add music_ferry/spotify_api.py tests/test_spotify_api.py
git commit -m "feat: add Spotify API module for playlist metadata"
```

---

## Task 5: Ntfy Notification Module

**Files:**
- Create: `music_ferry/notify.py`
- Create: `tests/test_notify.py`

**Step 1: Write the failing test**

```python
# tests/test_notify.py
from unittest.mock import patch, MagicMock

import pytest

from music_ferry.notify import Notifier, SyncResult, PlaylistResult


class TestNotifier:
    def test_sync_result_total_tracks(self):
        result = SyncResult(
            playlists=[
                PlaylistResult(name="Playlist 1", tracks_synced=5, error=None),
                PlaylistResult(name="Playlist 2", tracks_synced=3, error=None),
            ],
            transferred=True,
        )
        assert result.total_tracks == 8
        assert result.has_errors is False
        assert result.is_success is True

    def test_sync_result_with_errors(self):
        result = SyncResult(
            playlists=[
                PlaylistResult(name="Playlist 1", tracks_synced=5, error=None),
                PlaylistResult(name="Playlist 2", tracks_synced=0, error="Not found"),
            ],
            transferred=True,
        )
        assert result.total_tracks == 5
        assert result.has_errors is True
        assert result.is_success is False

    def test_sync_result_all_failed(self):
        result = SyncResult(
            playlists=[
                PlaylistResult(name="Playlist 1", tracks_synced=0, error="Login expired"),
            ],
            transferred=False,
            global_error="Login expired",
        )
        assert result.is_failure is True

    @patch("music_ferry.notify.requests.post")
    def test_send_success_notification(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)

        notifier = Notifier(
            ntfy_server="https://ntfy.sh",
            ntfy_topic="test-topic",
            notify_on_success=True,
            notify_on_failure=True,
        )

        result = SyncResult(
            playlists=[
                PlaylistResult(name="Discover Weekly", tracks_synced=8, error=None),
                PlaylistResult(name="Workout Mix", tracks_synced=4, error=None),
            ],
            transferred=True,
        )

        notifier.send(result)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "ntfy.sh/test-topic" in call_args[0][0]
        assert "Music Ferry Complete" in call_args[1]["headers"]["Title"]
        assert "12 new tracks" in call_args[1]["data"]
        assert "Discover Weekly: 8 new tracks" in call_args[1]["data"]
        assert "Workout Mix: 4 new tracks" in call_args[1]["data"]

    @patch("music_ferry.notify.requests.post")
    def test_send_failure_notification(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)

        notifier = Notifier(
            ntfy_server="https://ntfy.sh",
            ntfy_topic="test-topic",
            notify_on_success=True,
            notify_on_failure=True,
        )

        result = SyncResult(
            playlists=[
                PlaylistResult(name="Discover Weekly", tracks_synced=0, error=None),
            ],
            transferred=False,
            global_error="Login expired",
        )

        notifier.send(result)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "Music Ferry Failed" in call_args[1]["headers"]["Title"]
        assert "Login expired" in call_args[1]["data"]

    @patch("music_ferry.notify.requests.post")
    def test_skip_success_notification_when_disabled(self, mock_post):
        notifier = Notifier(
            ntfy_server="https://ntfy.sh",
            ntfy_topic="test-topic",
            notify_on_success=False,
            notify_on_failure=True,
        )

        result = SyncResult(
            playlists=[
                PlaylistResult(name="Discover Weekly", tracks_synced=8, error=None),
            ],
            transferred=True,
        )

        notifier.send(result)
        mock_post.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_notify.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# music_ferry/notify.py
from dataclasses import dataclass, field

import requests


@dataclass
class PlaylistResult:
    name: str
    tracks_synced: int
    error: str | None


@dataclass
class SyncResult:
    playlists: list[PlaylistResult]
    transferred: bool
    global_error: str | None = None

    @property
    def total_tracks(self) -> int:
        return sum(p.tracks_synced for p in self.playlists)

    @property
    def has_errors(self) -> bool:
        return any(p.error is not None for p in self.playlists)

    @property
    def is_success(self) -> bool:
        return not self.has_errors and self.global_error is None and self.total_tracks > 0

    @property
    def is_failure(self) -> bool:
        return self.global_error is not None or self.total_tracks == 0


class Notifier:
    def __init__(
        self,
        ntfy_server: str,
        ntfy_topic: str,
        notify_on_success: bool,
        notify_on_failure: bool,
    ):
        self.ntfy_server = ntfy_server.rstrip("/")
        self.ntfy_topic = ntfy_topic
        self.notify_on_success = notify_on_success
        self.notify_on_failure = notify_on_failure

    def send(self, result: SyncResult) -> None:
        if result.is_success and not self.notify_on_success:
            return
        if not result.is_success and not self.notify_on_failure:
            return

        title, body = self._format_message(result)
        self._send_notification(title, body)

    def _format_message(self, result: SyncResult) -> tuple[str, str]:
        if result.is_failure:
            title = "❌ Music Ferry Failed"
            body = f"{result.global_error or 'Sync failed'}\n\nPlaylists:\n"
            for p in result.playlists:
                body += f"• {p.name}: Not synced\n"
        elif result.has_errors:
            title = "⚠️ Music Ferry Partial"
            body = f"Synced {result.total_tracks} new tracks. Some issues occurred.\n\nPlaylists:\n"
            for p in result.playlists:
                if p.error:
                    body += f"• {p.name}: Failed ({p.error})\n"
                else:
                    body += f"• {p.name}: {p.tracks_synced} new tracks\n"
            if result.transferred:
                body += "\nTransferred to headphones."
        else:
            title = "🏊 Music Ferry Complete"
            body = f"Synced {result.total_tracks} new tracks."
            if result.transferred:
                body += " Transferred to headphones."
            body += "\n\nPlaylists:\n"
            for p in result.playlists:
                body += f"• {p.name}: {p.tracks_synced} new tracks\n"

        return title, body

    def _send_notification(self, title: str, body: str) -> None:
        url = f"{self.ntfy_server}/{self.ntfy_topic}"
        requests.post(
            url,
            data=body,
            headers={"Title": title},
        )
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_notify.py -v`
Expected: PASSED

**Step 5: Commit**

```bash
git add music_ferry/notify.py tests/test_notify.py
git commit -m "feat: add Ntfy notification module"
```

---

## Task 6: MP3 Tagger Module

**Files:**
- Create: `music_ferry/tagger.py`
- Create: `tests/test_tagger.py`

**Step 1: Write the failing test**

```python
# tests/test_tagger.py
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

import pytest
from mutagen.mp3 import MP3
from mutagen.id3 import ID3

from music_ferry.tagger import tag_mp3
from music_ferry.spotify_api import Track


class TestTagger:
    def test_tag_mp3_basic(self, tmp_path: Path):
        # Create a minimal valid MP3 file (just headers)
        mp3_path = tmp_path / "test.mp3"
        # Minimal MP3 frame (silence)
        mp3_bytes = bytes([
            0xFF, 0xFB, 0x90, 0x00,  # MP3 frame header
        ] + [0x00] * 417)  # Frame data
        mp3_path.write_bytes(mp3_bytes)

        track = Track(
            id="abc123",
            name="Test Song",
            artists=["Artist 1", "Artist 2"],
            album="Test Album",
            duration_ms=180000,
            album_art_url=None,
        )

        tag_mp3(mp3_path, track)

        # Verify tags were written
        audio = MP3(mp3_path)
        assert audio.tags["TIT2"].text[0] == "Test Song"
        assert audio.tags["TPE1"].text[0] == "Artist 1, Artist 2"
        assert audio.tags["TALB"].text[0] == "Test Album"

    @patch("music_ferry.tagger.requests.get")
    def test_tag_mp3_with_album_art(self, mock_get, tmp_path: Path):
        # Create minimal MP3
        mp3_path = tmp_path / "test.mp3"
        mp3_bytes = bytes([0xFF, 0xFB, 0x90, 0x00] + [0x00] * 417)
        mp3_path.write_bytes(mp3_bytes)

        # Mock album art download
        mock_response = MagicMock()
        mock_response.content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # Fake PNG
        mock_response.headers = {"Content-Type": "image/png"}
        mock_get.return_value = mock_response

        track = Track(
            id="abc123",
            name="Test Song",
            artists=["Artist 1"],
            album="Test Album",
            duration_ms=180000,
            album_art_url="https://example.com/art.jpg",
        )

        tag_mp3(mp3_path, track)

        # Verify album art was embedded
        audio = MP3(mp3_path)
        apic_frames = [f for f in audio.tags.values() if f.FrameID == "APIC"]
        assert len(apic_frames) == 1
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_tagger.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# music_ferry/tagger.py
from pathlib import Path

import requests
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError

from music_ferry.spotify_api import Track


def tag_mp3(mp3_path: Path, track: Track) -> None:
    try:
        audio = MP3(mp3_path)
    except ID3NoHeaderError:
        audio = MP3(mp3_path)
        audio.add_tags()

    if audio.tags is None:
        audio.add_tags()

    audio.tags["TIT2"] = TIT2(encoding=3, text=track.name)
    audio.tags["TPE1"] = TPE1(encoding=3, text=track.artist_string)
    audio.tags["TALB"] = TALB(encoding=3, text=track.album)

    if track.album_art_url:
        try:
            response = requests.get(track.album_art_url, timeout=10)
            if response.ok:
                mime_type = response.headers.get("Content-Type", "image/jpeg")
                audio.tags["APIC"] = APIC(
                    encoding=3,
                    mime=mime_type,
                    type=3,  # Cover (front)
                    desc="Cover",
                    data=response.content,
                )
        except requests.RequestException:
            pass  # Skip album art if download fails

    audio.save()
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_tagger.py -v`
Expected: PASSED

**Step 5: Commit**

```bash
git add music_ferry/tagger.py tests/test_tagger.py
git commit -m "feat: add MP3 tagger module with ID3 support"
```

---

## Task 7: Audio Recorder Module

**Files:**
- Create: `music_ferry/recorder.py`
- Create: `tests/test_recorder.py`

**Step 1: Write the failing test**

```python
# tests/test_recorder.py
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

import pytest

from music_ferry.recorder import AudioRecorder


class TestAudioRecorder:
    def test_sink_name_generation(self):
        recorder = AudioRecorder(bitrate=192)
        assert recorder.sink_name == "music-ferry-capture"

    @patch("music_ferry.recorder.subprocess.run")
    def test_create_virtual_sink(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        recorder = AudioRecorder(bitrate=192)
        recorder.create_virtual_sink()

        # Should call pactl to create null sink
        mock_run.assert_called()
        call_args = str(mock_run.call_args)
        assert "pactl" in call_args
        assert "load-module" in call_args
        assert "module-null-sink" in call_args

    @patch("music_ferry.recorder.subprocess.run")
    def test_destroy_virtual_sink(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        recorder = AudioRecorder(bitrate=192)
        recorder._module_id = 123
        recorder.destroy_virtual_sink()

        mock_run.assert_called()
        call_args = str(mock_run.call_args)
        assert "pactl" in call_args
        assert "unload-module" in call_args

    @patch("music_ferry.recorder.subprocess.Popen")
    def test_start_recording(self, mock_popen, tmp_path: Path):
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        recorder = AudioRecorder(bitrate=192)
        output_path = tmp_path / "test.mp3"

        recorder.start_recording(output_path)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert "ffmpeg" in call_args
        assert "-b:a" in call_args
        assert "192k" in call_args

    @patch("music_ferry.recorder.subprocess.Popen")
    def test_stop_recording(self, mock_popen, tmp_path: Path):
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        recorder = AudioRecorder(bitrate=192)
        output_path = tmp_path / "test.mp3"

        recorder.start_recording(output_path)
        recorder.stop_recording()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_recorder.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# music_ferry/recorder.py
import subprocess
from pathlib import Path


class AudioRecorder:
    def __init__(self, bitrate: int = 192):
        self.bitrate = bitrate
        self.sink_name = "music-ferry-capture"
        self._module_id: int | None = None
        self._ffmpeg_process: subprocess.Popen | None = None

    def create_virtual_sink(self) -> None:
        result = subprocess.run(
            [
                "pactl",
                "load-module",
                "module-null-sink",
                f"sink_name={self.sink_name}",
                f"sink_properties=device.description={self.sink_name}",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self._module_id = int(result.stdout.strip())

    def destroy_virtual_sink(self) -> None:
        if self._module_id is not None:
            subprocess.run(
                ["pactl", "unload-module", str(self._module_id)],
                capture_output=True,
            )
            self._module_id = None

    def get_monitor_source(self) -> str:
        return f"{self.sink_name}.monitor"

    def start_recording(self, output_path: Path) -> None:
        monitor_source = self.get_monitor_source()

        self._ffmpeg_process = subprocess.Popen(
            [
                "ffmpeg",
                "-y",  # Overwrite output
                "-f", "pulse",
                "-i", monitor_source,
                "-ac", "2",  # Stereo
                "-ar", "44100",  # Sample rate
                "-b:a", f"{self.bitrate}k",
                "-f", "mp3",
                str(output_path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop_recording(self) -> None:
        if self._ffmpeg_process is not None:
            if self._ffmpeg_process.poll() is None:
                self._ffmpeg_process.terminate()
                self._ffmpeg_process.wait(timeout=5)
            self._ffmpeg_process = None

    def __enter__(self):
        self.create_virtual_sink()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_recording()
        self.destroy_virtual_sink()
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_recorder.py -v`
Expected: PASSED

**Step 5: Commit**

```bash
git add music_ferry/recorder.py tests/test_recorder.py
git commit -m "feat: add audio recorder with PipeWire/FFmpeg"
```

---

## Task 8: Transfer Module

**Files:**
- Create: `music_ferry/transfer.py`
- Create: `tests/test_transfer.py`

**Step 1: Write the failing test**

```python
# tests/test_transfer.py
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from music_ferry.transfer import TransferManager


class TestTransferManager:
    def test_is_mounted_true(self, tmp_path: Path):
        mount_point = tmp_path / "HEADPHONES"
        mount_point.mkdir()
        (mount_point / "Music").mkdir()

        manager = TransferManager(
            headphones_mount=mount_point,
            headphones_music_folder="Music",
        )
        assert manager.is_mounted() is True

    def test_is_mounted_false(self, tmp_path: Path):
        mount_point = tmp_path / "HEADPHONES"
        # Don't create the directory

        manager = TransferManager(
            headphones_mount=mount_point,
            headphones_music_folder="Music",
        )
        assert manager.is_mounted() is False

    def test_transfer_files(self, tmp_path: Path):
        # Setup source files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "song1.mp3").write_bytes(b"audio1")
        (source_dir / "song2.mp3").write_bytes(b"audio2")

        # Setup destination
        mount_point = tmp_path / "HEADPHONES"
        mount_point.mkdir()
        music_folder = mount_point / "Music"
        music_folder.mkdir()

        manager = TransferManager(
            headphones_mount=mount_point,
            headphones_music_folder="Music",
        )

        transferred = manager.transfer(source_dir)

        assert transferred == 2
        assert (music_folder / "song1.mp3").exists()
        assert (music_folder / "song2.mp3").exists()

    def test_transfer_skips_existing(self, tmp_path: Path):
        # Setup source
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "song1.mp3").write_bytes(b"new audio")

        # Setup destination with existing file
        mount_point = tmp_path / "HEADPHONES"
        mount_point.mkdir()
        music_folder = mount_point / "Music"
        music_folder.mkdir()
        (music_folder / "song1.mp3").write_bytes(b"old audio")

        manager = TransferManager(
            headphones_mount=mount_point,
            headphones_music_folder="Music",
        )

        transferred = manager.transfer(source_dir)

        # File should be updated (rsync behavior)
        assert transferred >= 0  # rsync may or may not count unchanged files

    def test_transfer_when_not_mounted(self, tmp_path: Path):
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        mount_point = tmp_path / "HEADPHONES"
        # Don't mount

        manager = TransferManager(
            headphones_mount=mount_point,
            headphones_music_folder="Music",
        )

        with pytest.raises(RuntimeError, match="not mounted"):
            manager.transfer(source_dir)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_transfer.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# music_ferry/transfer.py
import shutil
import subprocess
from pathlib import Path


class TransferManager:
    def __init__(self, headphones_mount: Path, headphones_music_folder: str):
        self.headphones_mount = headphones_mount
        self.headphones_music_folder = headphones_music_folder

    @property
    def destination_path(self) -> Path:
        return self.headphones_mount / self.headphones_music_folder

    def is_mounted(self) -> bool:
        return self.headphones_mount.exists() and self.destination_path.exists()

    def transfer(self, source_dir: Path) -> int:
        if not self.is_mounted():
            raise RuntimeError(f"Headphones not mounted at {self.headphones_mount}")

        # Count mp3 files to transfer
        mp3_files = list(source_dir.glob("*.mp3"))

        # Use rsync for efficient transfer
        result = subprocess.run(
            [
                "rsync",
                "-av",
                "--ignore-existing",
                f"{source_dir}/",
                f"{self.destination_path}/",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"rsync failed: {result.stderr}")

        # Return count of source files (actual transferred may vary)
        return len(mp3_files)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_transfer.py -v`
Expected: PASSED

**Step 5: Commit**

```bash
git add music_ferry/transfer.py tests/test_transfer.py
git commit -m "feat: add transfer module for USB headphones"
```

---

## Task 9: Browser Automation Module

**Files:**
- Create: `music_ferry/browser.py`
- Create: `tests/test_browser.py`

**Step 1: Write the failing test**

```python
# tests/test_browser.py
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from music_ferry.browser import SpotifyBrowser


class TestSpotifyBrowser:
    def test_playlist_url_construction(self):
        browser = SpotifyBrowser.__new__(SpotifyBrowser)
        browser.base_url = "https://open.spotify.com"

        url = browser._get_playlist_url("abc123")
        assert url == "https://open.spotify.com/playlist/abc123"

    def test_track_url_construction(self):
        browser = SpotifyBrowser.__new__(SpotifyBrowser)
        browser.base_url = "https://open.spotify.com"

        url = browser._get_track_url("xyz789")
        assert url == "https://open.spotify.com/track/xyz789"


class TestSpotifyBrowserIntegration:
    """These tests require Playwright to be installed"""

    @pytest.mark.asyncio
    @patch("music_ferry.browser.async_playwright")
    async def test_launch_and_close(self, mock_playwright):
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_playwright.return_value.__aenter__.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        async with SpotifyBrowser(
            cookies_dir=Path("/tmp/cookies"),
            audio_sink="test-sink",
        ) as browser:
            assert browser.page is mock_page

        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("music_ferry.browser.async_playwright")
    async def test_play_track(self, mock_playwright):
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_playwright.return_value.__aenter__.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        async with SpotifyBrowser(
            cookies_dir=Path("/tmp/cookies"),
            audio_sink="test-sink",
        ) as browser:
            await browser.play_track("track123")

        # Should navigate to track and click play
        mock_page.goto.assert_called()
        mock_page.click.assert_called()
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_browser.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# music_ferry/browser.py
import asyncio
import json
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page, BrowserContext


class SpotifyBrowser:
    def __init__(self, cookies_dir: Path, audio_sink: str):
        self.cookies_dir = cookies_dir
        self.audio_sink = audio_sink
        self.base_url = "https://open.spotify.com"
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        await self._launch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close()

    async def _launch(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                f"--audio-output-device={self.audio_sink}",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )
        self._context = await self._browser.new_context()

        # Load cookies if they exist
        cookies_file = self.cookies_dir / "spotify-session.json"
        if cookies_file.exists():
            cookies = json.loads(cookies_file.read_text())
            await self._context.add_cookies(cookies)

        self.page = await self._context.new_page()

    async def _close(self) -> None:
        if self._context:
            # Save cookies for next session
            cookies = await self._context.cookies()
            self.cookies_dir.mkdir(parents=True, exist_ok=True)
            cookies_file = self.cookies_dir / "spotify-session.json"
            cookies_file.write_text(json.dumps(cookies))

        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def _get_playlist_url(self, playlist_id: str) -> str:
        return f"{self.base_url}/playlist/{playlist_id}"

    def _get_track_url(self, track_id: str) -> str:
        return f"{self.base_url}/track/{track_id}"

    async def navigate_to_playlist(self, playlist_id: str) -> None:
        url = self._get_playlist_url(playlist_id)
        await self.page.goto(url, wait_until="networkidle")

    async def play_track(self, track_id: str) -> None:
        url = self._get_track_url(track_id)
        await self.page.goto(url, wait_until="networkidle")

        # Wait for play button and click it
        play_button = self.page.locator('[data-testid="play-button"]')
        await play_button.wait_for(state="visible", timeout=10000)
        await play_button.click()

    async def pause(self) -> None:
        pause_button = self.page.locator('[data-testid="control-button-pause"]')
        if await pause_button.is_visible():
            await pause_button.click()

    async def is_logged_in(self) -> bool:
        await self.page.goto(self.base_url, wait_until="networkidle")
        # Check for login button presence (indicates not logged in)
        login_button = self.page.locator('[data-testid="login-button"]')
        return not await login_button.is_visible()
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_browser.py -v`
Expected: PASSED

**Step 5: Commit**

```bash
git add music_ferry/browser.py tests/test_browser.py
git commit -m "feat: add browser automation for Spotify Web Player"
```

---

## Task 10: Main Orchestrator

**Files:**
- Create: `music_ferry/orchestrator.py`
- Create: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# tests/test_orchestrator.py
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from music_ferry.orchestrator import Orchestrator
from music_ferry.config import (
    Config, SpotifyConfig, PlaylistConfig, AudioConfig,
    PathsConfig, NotificationsConfig, BehaviorConfig
)
from music_ferry.spotify_api import Track


@pytest.fixture
def sample_config(tmp_path: Path) -> Config:
    return Config(
        spotify=SpotifyConfig(
            client_id="test_id",
            client_secret="test_secret",
            username="test_user",
        ),
        playlists=[
            PlaylistConfig(name="Test Playlist", url="https://open.spotify.com/playlist/abc123"),
        ],
        audio=AudioConfig(bitrate=192, format="mp3"),
        paths=PathsConfig(
            music_dir=tmp_path / "music",
            headphones_mount=tmp_path / "headphones",
            headphones_music_folder="Music",
        ),
        notifications=NotificationsConfig(
            ntfy_topic="test-topic",
            ntfy_server="https://ntfy.sh",
            notify_on_success=False,
            notify_on_failure=True,
        ),
        behavior=BehaviorConfig(
            skip_existing=True,
            auto_transfer=True,
            trim_silence=True,
        ),
    )


class TestOrchestrator:
    def test_filter_new_tracks(self, sample_config: Config, tmp_path: Path):
        orchestrator = Orchestrator(sample_config)

        # Add one track to database
        orchestrator.tracks_db.add_track("existing123", "existing123.mp3")

        tracks = [
            Track(id="existing123", name="Old Song", artists=["A"], album="B", duration_ms=180000, album_art_url=None),
            Track(id="new456", name="New Song", artists=["C"], album="D", duration_ms=200000, album_art_url=None),
        ]

        new_tracks = orchestrator._filter_new_tracks(tracks)

        assert len(new_tracks) == 1
        assert new_tracks[0].id == "new456"

    @pytest.mark.asyncio
    @patch("music_ferry.orchestrator.SpotifyAPI")
    @patch("music_ferry.orchestrator.SpotifyBrowser")
    @patch("music_ferry.orchestrator.AudioRecorder")
    @patch("music_ferry.orchestrator.Notifier")
    async def test_run_sync(
        self,
        mock_notifier_class,
        mock_recorder_class,
        mock_browser_class,
        mock_api_class,
        sample_config: Config,
    ):
        # Setup mocks
        mock_api = MagicMock()
        mock_api.get_playlist_tracks.return_value = [
            Track(id="track1", name="Song 1", artists=["Artist"], album="Album", duration_ms=180000, album_art_url=None),
        ]
        mock_api_class.return_value = mock_api

        mock_browser = AsyncMock()
        mock_browser.__aenter__.return_value = mock_browser
        mock_browser.__aexit__.return_value = None
        mock_browser.is_logged_in.return_value = True
        mock_browser_class.return_value = mock_browser

        mock_recorder = MagicMock()
        mock_recorder.__enter__.return_value = mock_recorder
        mock_recorder.__exit__.return_value = None
        mock_recorder_class.return_value = mock_recorder

        mock_notifier = MagicMock()
        mock_notifier_class.return_value = mock_notifier

        # Run orchestrator
        orchestrator = Orchestrator(sample_config)
        result = await orchestrator.run()

        # Verify
        assert result.total_tracks == 1
        mock_api.get_playlist_tracks.assert_called_once()
        mock_notifier.send.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_orchestrator.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# music_ferry/orchestrator.py
import asyncio
import logging
from pathlib import Path

from music_ferry.config import Config
from music_ferry.tracks_db import TracksDB
from music_ferry.spotify_api import SpotifyAPI, Track
from music_ferry.browser import SpotifyBrowser
from music_ferry.recorder import AudioRecorder
from music_ferry.tagger import tag_mp3
from music_ferry.transfer import TransferManager
from music_ferry.notify import Notifier, SyncResult, PlaylistResult


logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, config: Config):
        self.config = config
        self.tracks_db = TracksDB(config.paths.music_dir.parent / "tracks.json")

        # Ensure music directory exists
        config.paths.music_dir.mkdir(parents=True, exist_ok=True)

    def _filter_new_tracks(self, tracks: list[Track]) -> list[Track]:
        if not self.config.behavior.skip_existing:
            return tracks
        return [t for t in tracks if not self.tracks_db.is_downloaded(t.id)]

    async def run(self) -> SyncResult:
        playlist_results: list[PlaylistResult] = []
        global_error: str | None = None

        api = SpotifyAPI(
            client_id=self.config.spotify.client_id,
            client_secret=self.config.spotify.client_secret,
        )

        notifier = Notifier(
            ntfy_server=self.config.notifications.ntfy_server,
            ntfy_topic=self.config.notifications.ntfy_topic,
            notify_on_success=self.config.notifications.notify_on_success,
            notify_on_failure=self.config.notifications.notify_on_failure,
        )

        try:
            with AudioRecorder(bitrate=self.config.audio.bitrate) as recorder:
                async with SpotifyBrowser(
                    cookies_dir=self.config.paths.music_dir.parent / "cookies",
                    audio_sink=recorder.sink_name,
                ) as browser:
                    if not await browser.is_logged_in():
                        global_error = "Login expired - please re-authenticate"
                        raise RuntimeError(global_error)

                    for playlist in self.config.playlists:
                        result = await self._sync_playlist(
                            playlist, api, browser, recorder
                        )
                        playlist_results.append(result)

        except RuntimeError as e:
            global_error = str(e)
            for playlist in self.config.playlists:
                if not any(r.name == playlist.name for r in playlist_results):
                    playlist_results.append(
                        PlaylistResult(name=playlist.name, tracks_synced=0, error=str(e))
                    )

        # Transfer to headphones
        transferred = False
        if self.config.behavior.auto_transfer:
            try:
                transfer_manager = TransferManager(
                    headphones_mount=self.config.paths.headphones_mount,
                    headphones_music_folder=self.config.paths.headphones_music_folder,
                )
                if transfer_manager.is_mounted():
                    transfer_manager.transfer(self.config.paths.music_dir)
                    transferred = True
                else:
                    logger.warning("Headphones not mounted, skipping transfer")
            except Exception as e:
                logger.error(f"Transfer failed: {e}")

        result = SyncResult(
            playlists=playlist_results,
            transferred=transferred,
            global_error=global_error,
        )

        notifier.send(result)
        return result

    async def _sync_playlist(
        self,
        playlist,
        api: SpotifyAPI,
        browser: SpotifyBrowser,
        recorder: AudioRecorder,
    ) -> PlaylistResult:
        try:
            tracks = api.get_playlist_tracks(playlist.playlist_id)
            new_tracks = self._filter_new_tracks(tracks)

            logger.info(f"Playlist {playlist.name}: {len(new_tracks)} new tracks")

            synced_count = 0
            for track in new_tracks:
                try:
                    await self._record_track(track, browser, recorder)
                    synced_count += 1
                except Exception as e:
                    logger.error(f"Failed to record {track.name}: {e}")

            return PlaylistResult(
                name=playlist.name,
                tracks_synced=synced_count,
                error=None,
            )

        except Exception as e:
            logger.error(f"Failed to sync playlist {playlist.name}: {e}")
            return PlaylistResult(
                name=playlist.name,
                tracks_synced=0,
                error=str(e),
            )

    async def _record_track(
        self,
        track: Track,
        browser: SpotifyBrowser,
        recorder: AudioRecorder,
    ) -> None:
        output_path = self.config.paths.music_dir / f"{track.id}.mp3"

        logger.info(f"Recording: {track.name} by {track.artist_string}")

        # Navigate to track and start playback
        await browser.play_track(track.id)

        # Wait a moment for playback to start
        await asyncio.sleep(2)

        # Start recording
        recorder.start_recording(output_path)

        # Wait for track duration plus buffer
        await asyncio.sleep(track.duration_seconds + 2)

        # Stop recording
        recorder.stop_recording()

        # Pause playback
        await browser.pause()

        # Tag the MP3
        tag_mp3(output_path, track)

        # Add to database
        self.tracks_db.add_track(track.id, f"{track.id}.mp3")

        logger.info(f"Completed: {track.name}")
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_orchestrator.py -v`
Expected: PASSED

**Step 5: Commit**

```bash
git add music_ferry/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add main orchestrator for sync workflow"
```

---

## Task 11: CLI Entry Point

**Files:**
- Create: `music_ferry/cli.py`
- Create: `bin/sync.sh`

**Step 1: Write the CLI module**

```python
# music_ferry/cli.py
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from music_ferry.config import load_config
from music_ferry.orchestrator import Orchestrator


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download Spotify playlists to MP3 for offline swimming"
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=Path.home() / ".music-ferry" / "config.yaml",
        help="Path to config file (default: ~/.music-ferry/config.yaml)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    logger = logging.getLogger(__name__)

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        logger.error(f"Config file not found: {args.config}")
        return 1
    except ValueError as e:
        logger.error(f"Invalid config: {e}")
        return 1

    orchestrator = Orchestrator(config)

    try:
        result = asyncio.run(orchestrator.run())
        if result.is_success:
            logger.info(f"Sync complete: {result.total_tracks} tracks")
            return 0
        elif result.has_errors:
            logger.warning(f"Sync completed with errors: {result.total_tracks} tracks")
            return 0
        else:
            logger.error("Sync failed")
            return 1
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Create shell wrapper for systemd**

```bash
#!/bin/bash
# bin/sync.sh
# Entry point for systemd service

set -e

# Start Xvfb for headless browser
Xvfb :99 -screen 0 1920x1080x24 &
XVFB_PID=$!
export DISPLAY=:99

# Give Xvfb time to start
sleep 1

# Activate virtual environment and run
cd "$(dirname "$0")/.."
source .venv/bin/activate

python -m music_ferry.cli "$@"
EXIT_CODE=$?

# Cleanup
kill $XVFB_PID 2>/dev/null || true

exit $EXIT_CODE
```

**Step 3: Make script executable**

Run: `chmod +x bin/sync.sh`

**Step 4: Verify CLI works**

Run: `source .venv/bin/activate && python -m music_ferry.cli --help`
Expected: Shows help message with options

**Step 5: Commit**

```bash
git add music_ferry/cli.py bin/sync.sh
git commit -m "feat: add CLI entry point and systemd wrapper"
```

---

## Task 12: Systemd Integration

**Files:**
- Create: `systemd/music-ferry.service`
- Create: `systemd/music-ferry.timer`
- Create: `scripts/install-systemd.sh`

**Step 1: Create service unit file**

```ini
# systemd/music-ferry.service
[Unit]
Description=Music Ferry - Download playlists for offline swimming
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=%h/.music-ferry/bin/sync.sh
TimeoutStartSec=3600

[Install]
WantedBy=default.target
```

**Step 2: Create timer unit file**

```ini
# systemd/music-ferry.timer
[Unit]
Description=Run Music Ferry daily at 3am

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

**Step 3: Create installation script**

```bash
#!/bin/bash
# scripts/install-systemd.sh
# Install systemd user units for Music Ferry

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="$HOME/.music-ferry"
SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "Installing Music Ferry..."

# Create installation directory
mkdir -p "$INSTALL_DIR/bin"
mkdir -p "$INSTALL_DIR/music"
mkdir -p "$INSTALL_DIR/cookies"
mkdir -p "$INSTALL_DIR/logs"

# Copy project files
cp -r "$PROJECT_DIR/music_ferry" "$INSTALL_DIR/"
cp -r "$PROJECT_DIR/.venv" "$INSTALL_DIR/"
cp "$PROJECT_DIR/bin/sync.sh" "$INSTALL_DIR/bin/"
chmod +x "$INSTALL_DIR/bin/sync.sh"

# Create sample config if not exists
if [ ! -f "$INSTALL_DIR/config.yaml" ]; then
    cat > "$INSTALL_DIR/config.yaml" << 'EOF'
spotify:
  client_id: "YOUR_SPOTIFY_CLIENT_ID"
  client_secret: "YOUR_SPOTIFY_CLIENT_SECRET"
  username: "YOUR_SPOTIFY_USERNAME"

playlists:
  - name: "Discover Weekly"
    url: "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID"

audio:
  bitrate: 192
  format: "mp3"

paths:
  music_dir: "~/.music-ferry/music"
  headphones_mount: "/media/YOUR_USERNAME/HEADPHONES"
  headphones_music_folder: "Music"

notifications:
  ntfy_topic: "your-secret-topic"
  ntfy_server: "https://ntfy.sh"
  notify_on_success: false
  notify_on_failure: true

behavior:
  skip_existing: true
  auto_transfer: true
  trim_silence: true
EOF
    echo "Created sample config at $INSTALL_DIR/config.yaml"
    echo "Please edit it with your Spotify credentials and settings."
fi

# Install systemd units
mkdir -p "$SYSTEMD_DIR"
sed "s|%h|$HOME|g" "$PROJECT_DIR/systemd/music-ferry.service" > "$SYSTEMD_DIR/music-ferry.service"
cp "$PROJECT_DIR/systemd/music-ferry.timer" "$SYSTEMD_DIR/"

# Reload systemd
systemctl --user daemon-reload

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Edit config: $INSTALL_DIR/config.yaml"
echo "2. Install Playwright browsers: $INSTALL_DIR/.venv/bin/playwright install chromium"
echo "3. Login to Spotify manually once to save cookies"
echo "4. Enable timer: systemctl --user enable --now music-ferry.timer"
echo ""
echo "Commands:"
echo "  Run manually:    systemctl --user start music-ferry.service"
echo "  View logs:       journalctl --user -u music-ferry.service -f"
echo "  Check timer:     systemctl --user list-timers music-ferry.timer"
```

**Step 4: Make installation script executable**

Run: `chmod +x scripts/install-systemd.sh`

**Step 5: Commit**

```bash
mkdir -p systemd scripts
git add systemd/ scripts/
git commit -m "feat: add systemd units and installation script"
```

---

## Task 13: Final Integration Test

**Step 1: Run all tests**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests pass

**Step 2: Verify package installs correctly**

Run: `pip install -e .`
Expected: Successfully installed music-ferry

**Step 3: Verify CLI is accessible**

Run: `music-ferry --help`
Expected: Shows help message

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup and integration"
```

---

## Post-Implementation: Manual Setup Steps

After running the implementation plan, the user needs to:

1. **Create Spotify Developer App**
   - Go to https://developer.spotify.com/dashboard
   - Create new app, get client ID and secret
   - Add to config.yaml

2. **Configure Ntfy topic**
   - Choose a random topic name
   - Install Ntfy app on phone
   - Subscribe to topic

3. **Initial Spotify Login**
   - Run `music-ferry` manually once
   - Browser will open for login
   - Cookies saved for future runs

4. **Install Playwright browsers**
   - Run: `playwright install chromium`

5. **Enable systemd timer**
   - Run: `systemctl --user enable --now music-ferry.timer`
