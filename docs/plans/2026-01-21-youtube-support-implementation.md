# YouTube Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add YouTube playlist download support alongside existing Spotify functionality.

**Architecture:** Symmetric source handling with separate libraries (`spotify/` and `youtube/` folders), shared audio/behavior settings, and merged flat output to headphones. YouTube uses yt-dlp for direct download (no browser recording).

**Tech Stack:** yt-dlp for YouTube downloads, existing mutagen for tagging, argparse for CLI flags.

---

## Task 1: Add yt-dlp Dependency

**Files:**
- Modify: `pyproject.toml:10-17`

**Step 1: Add yt-dlp to dependencies**

```toml
dependencies = [
    "playwright>=1.40.0",
    "spotipy>=2.23.0",
    "ffmpeg-python>=0.2.0",
    "mutagen>=1.47.0",
    "pyyaml>=6.0",
    "requests>=2.31.0",
    "yt-dlp>=2024.0.0",
]
```

**Step 2: Install the new dependency**

Run: `pip install -e ".[dev]"`
Expected: Successfully installs yt-dlp

**Step 3: Verify yt-dlp is available**

Run: `python -c "import yt_dlp; print(yt_dlp.version.__version__)"`
Expected: Prints version number

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add yt-dlp dependency for YouTube support"
```

---

## Task 2: Add Source Field to Track Dataclass

**Files:**
- Modify: `spotify_swimmer/spotify_api.py:8-24`
- Test: `tests/test_spotify_api.py`

**Step 1: Write the failing test**

Create `tests/test_track_source.py`:

```python
# tests/test_track_source.py
import pytest
from spotify_swimmer.spotify_api import Track


class TestTrackSource:
    def test_track_defaults_to_spotify_source(self):
        track = Track(
            id="abc123",
            name="Test Song",
            artists=["Artist"],
            album="Album",
            duration_ms=180000,
            album_art_url=None,
        )
        assert track.source == "spotify"

    def test_track_can_have_youtube_source(self):
        track = Track(
            id="dQw4w9WgXcQ",
            name="Test Video",
            artists=["Channel Name"],
            album="Playlist Name",
            duration_ms=213000,
            album_art_url="https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
            source="youtube",
        )
        assert track.source == "youtube"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_track_source.py -v`
Expected: FAIL with "unexpected keyword argument 'source'"

**Step 3: Add source field to Track dataclass**

In `spotify_swimmer/spotify_api.py`, update the Track dataclass:

```python
@dataclass
class Track:
    id: str
    name: str
    artists: list[str]
    album: str
    duration_ms: int
    album_art_url: str | None
    source: str = "spotify"

    @property
    def duration_seconds(self) -> int:
        return self.duration_ms // 1000

    @property
    def artist_string(self) -> str:
        return ", ".join(self.artists)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_track_source.py -v`
Expected: PASS

**Step 5: Run all tests to ensure no regressions**

Run: `pytest -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add spotify_swimmer/spotify_api.py tests/test_track_source.py
git commit -m "feat: add source field to Track dataclass"
```

---

## Task 3: Update Config for YouTube Support

**Files:**
- Modify: `spotify_swimmer/config.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing test for new config structure**

Add to `tests/test_config.py`:

```python
class TestYouTubeConfig:
    def test_load_config_with_youtube_section(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "spotify": {
                "enabled": True,
                "client_id": "test_id",
                "client_secret": "test_secret",
                "username": "test_user",
                "playlists": [
                    {"name": "Test Playlist", "url": "https://open.spotify.com/playlist/abc123"}
                ],
            },
            "youtube": {
                "enabled": True,
                "playlists": [
                    {"name": "YT Playlist", "url": "https://www.youtube.com/playlist?list=PLxxx"}
                ],
            },
            "audio": {"bitrate": 192, "format": "mp3"},
            "paths": {
                "music_dir": "~/.spotify-swimmer",
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
                "trim_silence": True,
            },
        }))

        config = load_config(config_file)

        assert config.spotify.enabled is True
        assert len(config.spotify.playlists) == 1
        assert config.spotify.playlists[0].name == "Test Playlist"
        assert config.youtube.enabled is True
        assert len(config.youtube.playlists) == 1
        assert config.youtube.playlists[0].name == "YT Playlist"

    def test_load_config_youtube_disabled_by_default(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "spotify": {
                "client_id": "test_id",
                "client_secret": "test_secret",
                "username": "test_user",
                "playlists": [
                    {"name": "Test", "url": "https://open.spotify.com/playlist/abc123"}
                ],
            },
            "audio": {"bitrate": 192, "format": "mp3"},
            "paths": {
                "music_dir": "~/.spotify-swimmer",
                "headphones_mount": "/media/user/HEADPHONES",
                "headphones_music_folder": "Music",
            },
            "notifications": {
                "ntfy_topic": "test-topic",
                "ntfy_server": "https://ntfy.sh",
            },
            "behavior": {"skip_existing": True, "trim_silence": True},
        }))

        config = load_config(config_file)

        assert config.spotify.enabled is True
        assert config.youtube.enabled is False
        assert len(config.youtube.playlists) == 0

    def test_load_config_migrates_root_playlists(self, tmp_path: Path):
        """Test backward compatibility: playlists at root level migrate to spotify.playlists."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "spotify": {
                "client_id": "test_id",
                "client_secret": "test_secret",
                "username": "test_user",
            },
            "playlists": [
                {"name": "Old Format", "url": "https://open.spotify.com/playlist/abc123"}
            ],
            "audio": {"bitrate": 192, "format": "mp3"},
            "paths": {
                "music_dir": "~/.spotify-swimmer",
                "headphones_mount": "/media/user/HEADPHONES",
                "headphones_music_folder": "Music",
            },
            "notifications": {
                "ntfy_topic": "test-topic",
                "ntfy_server": "https://ntfy.sh",
            },
            "behavior": {"skip_existing": True, "trim_silence": True},
        }))

        config = load_config(config_file)

        assert len(config.spotify.playlists) == 1
        assert config.spotify.playlists[0].name == "Old Format"


class TestYouTubePlaylistConfig:
    def test_youtube_playlist_id_extraction(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "spotify": {
                "client_id": "test_id",
                "client_secret": "test_secret",
                "username": "test_user",
                "playlists": [],
            },
            "youtube": {
                "enabled": True,
                "playlists": [
                    {"name": "Test", "url": "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"}
                ],
            },
            "audio": {"bitrate": 192, "format": "mp3"},
            "paths": {
                "music_dir": "~/.spotify-swimmer",
                "headphones_mount": "/media/user/HEADPHONES",
                "headphones_music_folder": "Music",
            },
            "notifications": {"ntfy_topic": "test", "ntfy_server": "https://ntfy.sh"},
            "behavior": {"skip_existing": True, "trim_silence": True},
        }))

        config = load_config(config_file)

        assert config.youtube.playlists[0].playlist_id == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::TestYouTubeConfig -v`
Expected: FAIL with attribute errors

**Step 3: Update config.py with new structure**

Replace `spotify_swimmer/config.py`:

```python
# spotify_swimmer/config.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import re

import yaml


@dataclass
class PlaylistConfig:
    name: str
    url: str

    @property
    def playlist_id(self) -> str:
        # Try Spotify format first
        spotify_match = re.search(r"playlist/([a-zA-Z0-9]+)", self.url)
        if spotify_match:
            return spotify_match.group(1)
        # Try YouTube format
        youtube_match = re.search(r"[?&]list=([a-zA-Z0-9_-]+)", self.url)
        if youtube_match:
            return youtube_match.group(1)
        raise ValueError(f"Invalid playlist URL: {self.url}")


@dataclass
class SpotifyConfig:
    client_id: str
    client_secret: str
    username: str
    enabled: bool = True
    playlists: list[PlaylistConfig] = field(default_factory=list)


@dataclass
class YouTubeConfig:
    enabled: bool = False
    playlists: list[PlaylistConfig] = field(default_factory=list)


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
    trim_silence: bool = True


@dataclass
class Config:
    spotify: SpotifyConfig
    youtube: YouTubeConfig
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

    # Handle backward compatibility: migrate root-level playlists to spotify.playlists
    spotify_playlists_data = spotify_data.get("playlists", [])
    if not spotify_playlists_data and "playlists" in data:
        spotify_playlists_data = data.get("playlists", [])

    spotify_playlists = [
        PlaylistConfig(name=p["name"], url=p["url"])
        for p in spotify_playlists_data
    ]

    spotify = SpotifyConfig(
        client_id=spotify_data["client_id"],
        client_secret=spotify_data["client_secret"],
        username=spotify_data["username"],
        enabled=spotify_data.get("enabled", True),
        playlists=spotify_playlists,
    )

    # YouTube config (optional section)
    youtube_data = data.get("youtube", {})
    youtube_playlists = [
        PlaylistConfig(name=p["name"], url=p["url"])
        for p in youtube_data.get("playlists", [])
    ]

    youtube = YouTubeConfig(
        enabled=youtube_data.get("enabled", False) if youtube_data else False,
        playlists=youtube_playlists,
    )

    audio_data = data.get("audio", {})
    audio = AudioConfig(
        bitrate=audio_data.get("bitrate", 192),
        format=audio_data.get("format", "mp3"),
    )

    paths_data = data.get("paths", {})
    paths = PathsConfig(
        music_dir=paths_data.get("music_dir", "~/.spotify-swimmer"),
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
        trim_silence=behavior_data.get("trim_silence", True),
    )

    return Config(
        spotify=spotify,
        youtube=youtube,
        audio=audio,
        paths=paths,
        notifications=notifications,
        behavior=behavior,
    )
```

**Step 4: Update existing tests in test_config.py**

Update `tests/test_config.py` to use new config structure (playlists under spotify):

```python
# tests/test_config.py
import tempfile
from pathlib import Path

import pytest
import yaml

from spotify_swimmer.config import Config, load_config


class TestConfig:
    def test_load_valid_config(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "spotify": {
                "client_id": "test_id",
                "client_secret": "test_secret",
                "username": "test_user",
                "playlists": [
                    {"name": "Test Playlist", "url": "https://open.spotify.com/playlist/abc123"}
                ],
            },
            "audio": {"bitrate": 192, "format": "mp3"},
            "paths": {
                "music_dir": "~/.spotify-swimmer/music",
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
                "trim_silence": True,
            },
        }))

        config = load_config(config_file)

        assert config.spotify.client_id == "test_id"
        assert config.spotify.client_secret == "test_secret"
        assert config.spotify.username == "test_user"
        assert len(config.spotify.playlists) == 1
        assert config.spotify.playlists[0].name == "Test Playlist"
        assert config.audio.bitrate == 192
        assert config.paths.music_dir == Path.home() / ".spotify-swimmer" / "music"
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
                "playlists": [
                    {"name": "Test", "url": "https://open.spotify.com/playlist/37i9dQZEVXcQ9COmYvdajy"}
                ],
            },
            "audio": {"bitrate": 192, "format": "mp3"},
            "paths": {
                "music_dir": "~/.spotify-swimmer/music",
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
                "trim_silence": True,
            },
        }))

        config = load_config(config_file)
        assert config.spotify.playlists[0].playlist_id == "37i9dQZEVXcQ9COmYvdajy"
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add spotify_swimmer/config.py tests/test_config.py
git commit -m "feat: update config structure for YouTube support"
```

---

## Task 4: Create YouTube Downloader Module

**Files:**
- Create: `spotify_swimmer/youtube/__init__.py`
- Create: `spotify_swimmer/youtube/downloader.py`
- Test: `tests/test_youtube_downloader.py`

**Step 1: Create the youtube package**

Create `spotify_swimmer/youtube/__init__.py`:

```python
# spotify_swimmer/youtube/__init__.py
from spotify_swimmer.youtube.downloader import YouTubeDownloader

__all__ = ["YouTubeDownloader"]
```

**Step 2: Write the failing tests**

Create `tests/test_youtube_downloader.py`:

```python
# tests/test_youtube_downloader.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import json

from spotify_swimmer.youtube.downloader import YouTubeDownloader
from spotify_swimmer.spotify_api import Track


class TestYouTubeDownloader:
    @pytest.fixture
    def downloader(self, tmp_path: Path):
        return YouTubeDownloader(output_dir=tmp_path / "music", bitrate=192)

    def test_init_creates_output_dir(self, tmp_path: Path):
        output_dir = tmp_path / "youtube" / "music"
        downloader = YouTubeDownloader(output_dir=output_dir, bitrate=192)
        assert output_dir.exists()

    @patch("spotify_swimmer.youtube.downloader.yt_dlp.YoutubeDL")
    def test_get_playlist_tracks_returns_tracks(self, mock_ydl_class, downloader):
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

        mock_ydl.extract_info.return_value = {
            "title": "Test Playlist",
            "entries": [
                {
                    "id": "dQw4w9WgXcQ",
                    "title": "Rick Astley - Never Gonna Give You Up",
                    "channel": "Rick Astley",
                    "duration": 213,
                    "thumbnail": "https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
                },
                {
                    "id": "abc123xyz",
                    "title": "Another Video",
                    "channel": "Some Channel",
                    "duration": 180,
                    "thumbnail": None,
                },
            ],
        }

        tracks = downloader.get_playlist_tracks(
            "https://www.youtube.com/playlist?list=PLtest",
            playlist_name="Test Playlist",
        )

        assert len(tracks) == 2
        assert tracks[0].id == "dQw4w9WgXcQ"
        assert tracks[0].name == "Rick Astley - Never Gonna Give You Up"
        assert tracks[0].artists == ["Rick Astley"]
        assert tracks[0].album == "Test Playlist"
        assert tracks[0].duration_ms == 213000
        assert tracks[0].source == "youtube"

    @patch("spotify_swimmer.youtube.downloader.yt_dlp.YoutubeDL")
    def test_download_track_calls_ytdlp(self, mock_ydl_class, downloader, tmp_path):
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

        track = Track(
            id="dQw4w9WgXcQ",
            name="Never Gonna Give You Up",
            artists=["Rick Astley"],
            album="Test Playlist",
            duration_ms=213000,
            album_art_url="https://example.com/thumb.jpg",
            source="youtube",
        )

        result = downloader.download_track(track)

        mock_ydl.download.assert_called_once()
        assert result == downloader.output_dir / "dQw4w9WgXcQ.mp3"

    @patch("spotify_swimmer.youtube.downloader.time.sleep")
    @patch("spotify_swimmer.youtube.downloader.random.uniform")
    def test_download_tracks_with_delay(self, mock_random, mock_sleep, downloader):
        mock_random.return_value = 10.0

        tracks = [
            Track(id="vid1", name="Video 1", artists=["Ch1"], album="PL",
                  duration_ms=100000, album_art_url=None, source="youtube"),
            Track(id="vid2", name="Video 2", artists=["Ch2"], album="PL",
                  duration_ms=100000, album_art_url=None, source="youtube"),
        ]

        with patch.object(downloader, "download_track", return_value=Path("/fake.mp3")):
            count = downloader.download_tracks(tracks)

        assert count == 2
        # Should have slept between downloads (1 time for 2 tracks)
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(10.0)
```

**Step 3: Run test to verify it fails**

Run: `pytest tests/test_youtube_downloader.py -v`
Expected: FAIL with "No module named 'spotify_swimmer.youtube'"

**Step 4: Create the downloader module**

Create `spotify_swimmer/youtube/downloader.py`:

```python
# spotify_swimmer/youtube/downloader.py
import logging
import random
import time
from pathlib import Path

import yt_dlp

from spotify_swimmer.spotify_api import Track

logger = logging.getLogger(__name__)


class YouTubeDownloader:
    def __init__(self, output_dir: Path, bitrate: int = 192):
        self.output_dir = output_dir
        self.bitrate = bitrate
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_playlist_tracks(
        self, playlist_url: str, playlist_name: str
    ) -> list[Track]:
        """Fetch playlist metadata without downloading.

        Returns list of Track objects with source="youtube".
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)

        tracks = []
        for entry in info.get("entries", []):
            if entry is None:
                continue

            track = Track(
                id=entry["id"],
                name=entry.get("title", "Unknown"),
                artists=[entry.get("channel", "Unknown")],
                album=playlist_name,
                duration_ms=int(entry.get("duration", 0) * 1000),
                album_art_url=entry.get("thumbnail"),
                source="youtube",
            )
            tracks.append(track)

        return tracks

    def download_track(self, track: Track) -> Path:
        """Download a single track as MP3.

        Returns path to the downloaded file.
        """
        output_path = self.output_dir / f"{track.id}.mp3"
        output_template = str(self.output_dir / f"{track.id}.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(self.bitrate),
                },
                {
                    "key": "EmbedThumbnail",
                },
                {
                    "key": "FFmpegMetadata",
                },
            ],
            "writethumbnail": True,
            "quiet": True,
            "no_warnings": True,
        }

        video_url = f"https://www.youtube.com/watch?v={track.id}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        return output_path

    def download_tracks(
        self,
        tracks: list[Track],
        on_progress: callable = None,
    ) -> int:
        """Download multiple tracks with random delays.

        Returns count of successfully downloaded tracks.
        """
        downloaded = 0

        for i, track in enumerate(tracks):
            try:
                logger.info(f"Downloading: {track.name} by {track.artist_string}")
                self.download_track(track)
                downloaded += 1

                if on_progress:
                    on_progress(i + 1, len(tracks), track)

                # Random delay between downloads (except after last)
                if i < len(tracks) - 1:
                    delay = random.uniform(5, 15)
                    logger.debug(f"Waiting {delay:.1f}s before next download")
                    time.sleep(delay)

            except Exception as e:
                logger.error(f"Failed to download {track.name}: {e}")

        return downloaded
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_youtube_downloader.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add spotify_swimmer/youtube/ tests/test_youtube_downloader.py
git commit -m "feat: add YouTube downloader module with yt-dlp"
```

---

## Task 5: Add CLI Flags for Source Selection

**Files:**
- Modify: `spotify_swimmer/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing tests**

Create `tests/test_cli_sources.py`:

```python
# tests/test_cli_sources.py
import pytest
from spotify_swimmer.cli import parse_args


class TestCLISourceFlags:
    def test_sync_no_flags_syncs_all(self):
        args = parse_args(["sync"])
        assert args.command == "sync"
        assert args.spotify is False
        assert args.youtube is False
        # No flags means sync all enabled sources

    def test_sync_spotify_only(self):
        args = parse_args(["sync", "--spotify"])
        assert args.spotify is True
        assert args.youtube is False

    def test_sync_youtube_only(self):
        args = parse_args(["sync", "--youtube"])
        assert args.spotify is False
        assert args.youtube is True

    def test_sync_both_flags(self):
        args = parse_args(["sync", "--spotify", "--youtube"])
        assert args.spotify is True
        assert args.youtube is True

    def test_transfer_no_flags_transfers_all(self):
        args = parse_args(["transfer"])
        assert args.command == "transfer"
        assert args.spotify is False
        assert args.youtube is False

    def test_transfer_spotify_only(self):
        args = parse_args(["transfer", "--spotify"])
        assert args.spotify is True
        assert args.youtube is False

    def test_transfer_youtube_only(self):
        args = parse_args(["transfer", "--youtube"])
        assert args.spotify is False
        assert args.youtube is True

    def test_global_flags_still_work(self):
        args = parse_args(["-v", "-c", "/custom/path.yaml", "sync", "--youtube"])
        assert args.verbose is True
        assert str(args.config) == "/custom/path.yaml"
        assert args.youtube is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_sources.py -v`
Expected: FAIL with "Namespace has no attribute 'spotify'"

**Step 3: Update CLI with source flags**

Update `spotify_swimmer/cli.py`:

```python
# spotify_swimmer/cli.py
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from spotify_swimmer.config import load_config


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _add_source_flags(parser: argparse.ArgumentParser) -> None:
    """Add --spotify and --youtube flags to a subparser."""
    parser.add_argument(
        "--spotify",
        action="store_true",
        help="Only process Spotify playlists",
    )
    parser.add_argument(
        "--youtube",
        action="store_true",
        help="Only process YouTube playlists",
    )


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Spotify and YouTube playlists to MP3 for offline swimming"
    )

    # Global arguments
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=Path.home() / ".spotify-swimmer" / "config.yaml",
        help="Path to config file (default: ~/.spotify-swimmer/config.yaml)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync command
    sync_parser = subparsers.add_parser(
        "sync",
        help="Download new tracks and clean up orphans (no transfer)",
    )
    _add_source_flags(sync_parser)

    # transfer command
    transfer_parser = subparsers.add_parser(
        "transfer",
        help="Interactive transfer to headphones",
    )
    _add_source_flags(transfer_parser)

    return parser.parse_args(args)


def _resolve_sources(args: argparse.Namespace, config) -> tuple[bool, bool]:
    """Resolve which sources to process based on flags and config.

    Returns (sync_spotify, sync_youtube) booleans.
    """
    # If both flags are False, use config enabled settings
    if not args.spotify and not args.youtube:
        return config.spotify.enabled, config.youtube.enabled

    # Otherwise, use explicit flags
    return args.spotify, args.youtube


def cmd_sync(config, args) -> int:
    """Run sync command - download new tracks, cleanup orphans."""
    from spotify_swimmer.orchestrator import Orchestrator

    logger = logging.getLogger(__name__)

    sync_spotify, sync_youtube = _resolve_sources(args, config)

    orchestrator = Orchestrator(config)

    try:
        result = asyncio.run(
            orchestrator.run(sync_spotify=sync_spotify, sync_youtube=sync_youtube)
        )
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


def cmd_transfer(config, args) -> int:
    """Run transfer command - interactive headphones transfer."""
    from spotify_swimmer.transfer import InteractiveTransfer

    logger = logging.getLogger(__name__)

    sync_spotify, sync_youtube = _resolve_sources(args, config)

    sources = []
    if sync_spotify:
        sources.append("spotify")
    if sync_youtube:
        sources.append("youtube")

    try:
        transfer = InteractiveTransfer(config, sources=sources if sources else None)
        return transfer.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


def main() -> int:
    args = parse_args()
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

    if args.command == "sync":
        return cmd_sync(config, args)
    elif args.command == "transfer":
        return cmd_transfer(config, args)
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_sources.py -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add spotify_swimmer/cli.py tests/test_cli_sources.py
git commit -m "feat: add --spotify and --youtube flags to CLI"
```

---

## Task 6: Update Orchestrator for Multi-Source Support

**Files:**
- Modify: `spotify_swimmer/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing tests**

Create `tests/test_orchestrator_sources.py`:

```python
# tests/test_orchestrator_sources.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from spotify_swimmer.orchestrator import Orchestrator


class TestOrchestratorMultiSource:
    @pytest.fixture
    def mock_config(self, tmp_path: Path):
        config = MagicMock()
        config.spotify.enabled = True
        config.spotify.client_id = "test_id"
        config.spotify.client_secret = "test_secret"
        config.spotify.playlists = []

        config.youtube.enabled = True
        config.youtube.playlists = []

        config.paths.music_dir = tmp_path
        config.audio.bitrate = 192
        config.behavior.skip_existing = True
        config.behavior.trim_silence = True
        config.notifications.ntfy_server = "https://ntfy.sh"
        config.notifications.ntfy_topic = "test"
        config.notifications.notify_on_success = False
        config.notifications.notify_on_failure = False

        return config

    def test_orchestrator_has_separate_libraries(self, mock_config, tmp_path):
        orchestrator = Orchestrator(mock_config)

        assert orchestrator.spotify_library.db_path == tmp_path / "spotify" / "library.json"
        assert orchestrator.youtube_library.db_path == tmp_path / "youtube" / "library.json"

    def test_orchestrator_creates_source_directories(self, mock_config, tmp_path):
        orchestrator = Orchestrator(mock_config)

        assert (tmp_path / "spotify" / "music").exists()
        assert (tmp_path / "youtube" / "music").exists()

    @pytest.mark.asyncio
    async def test_run_with_spotify_only(self, mock_config):
        with patch.object(Orchestrator, "_sync_spotify", new_callable=AsyncMock) as mock_spotify:
            with patch.object(Orchestrator, "_sync_youtube", new_callable=AsyncMock) as mock_youtube:
                mock_spotify.return_value = []
                mock_youtube.return_value = []

                orchestrator = Orchestrator(mock_config)
                await orchestrator.run(sync_spotify=True, sync_youtube=False)

                mock_spotify.assert_called_once()
                mock_youtube.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_with_youtube_only(self, mock_config):
        with patch.object(Orchestrator, "_sync_spotify", new_callable=AsyncMock) as mock_spotify:
            with patch.object(Orchestrator, "_sync_youtube", new_callable=AsyncMock) as mock_youtube:
                mock_spotify.return_value = []
                mock_youtube.return_value = []

                orchestrator = Orchestrator(mock_config)
                await orchestrator.run(sync_spotify=False, sync_youtube=True)

                mock_spotify.assert_not_called()
                mock_youtube.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_both_sources(self, mock_config):
        with patch.object(Orchestrator, "_sync_spotify", new_callable=AsyncMock) as mock_spotify:
            with patch.object(Orchestrator, "_sync_youtube", new_callable=AsyncMock) as mock_youtube:
                mock_spotify.return_value = []
                mock_youtube.return_value = []

                orchestrator = Orchestrator(mock_config)
                await orchestrator.run(sync_spotify=True, sync_youtube=True)

                mock_spotify.assert_called_once()
                mock_youtube.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator_sources.py -v`
Expected: FAIL with attribute errors

**Step 3: Update orchestrator for multi-source support**

Update `spotify_swimmer/orchestrator.py`:

```python
# spotify_swimmer/orchestrator.py
import asyncio
import logging
from pathlib import Path

from spotify_swimmer.config import Config, PlaylistConfig
from spotify_swimmer.library import Library
from spotify_swimmer.spotify_api import SpotifyAPI, Track
from spotify_swimmer.browser import SpotifyBrowser
from spotify_swimmer.recorder import AudioRecorder
from spotify_swimmer.tagger import tag_mp3
from spotify_swimmer.notify import Notifier, SyncResult, PlaylistResult
from spotify_swimmer.youtube import YouTubeDownloader


logger = logging.getLogger(__name__)

PLAYLIST_MODE_THRESHOLD = 0.7  # Use playlist mode when >= 70% of tracks are new


class Orchestrator:
    def __init__(self, config: Config):
        self.config = config

        # Setup directories
        spotify_base = config.paths.music_dir / "spotify"
        youtube_base = config.paths.music_dir / "youtube"

        spotify_base.mkdir(parents=True, exist_ok=True)
        youtube_base.mkdir(parents=True, exist_ok=True)
        (spotify_base / "music").mkdir(exist_ok=True)
        (youtube_base / "music").mkdir(exist_ok=True)

        # Setup libraries with migration support
        old_library = config.paths.music_dir.parent / "library.json"
        self.spotify_library = Library(
            spotify_base / "library.json",
            migrate_from=old_library if old_library.exists() else None,
        )
        self.youtube_library = Library(youtube_base / "library.json")

        # Paths for music storage
        self.spotify_music_dir = spotify_base / "music"
        self.youtube_music_dir = youtube_base / "music"

    def _filter_new_tracks(
        self, tracks: list[Track], library: Library
    ) -> list[Track]:
        if not self.config.behavior.skip_existing:
            return tracks
        return [t for t in tracks if not library.is_downloaded(t.id)]

    @staticmethod
    def _select_playback_mode(new_count: int, total_count: int) -> str:
        """Select playback mode based on ratio of new tracks.

        Returns 'playlist' if >= 70% of tracks are new (looks more natural),
        otherwise returns 'individual' for targeted downloads.
        """
        if total_count == 0:
            return "individual"
        ratio = new_count / total_count
        if ratio >= PLAYLIST_MODE_THRESHOLD:
            return "playlist"
        return "individual"

    def _cleanup_orphaned_tracks(self, library: Library, music_dir: Path) -> int:
        """Delete orphaned tracks from disk and library. Returns count deleted."""
        orphaned = library.get_orphaned_tracks()
        deleted_count = 0

        for track in orphaned:
            mp3_path = music_dir / track.filename

            # Delete MP3 file if exists
            if mp3_path.exists():
                mp3_path.unlink()
                logger.info(f"Deleted orphaned file: {track.filename}")

            # Remove from library
            library.delete_track(track.id)
            deleted_count += 1
            logger.info(f"Removed orphaned track: {track.title} by {track.artist}")

        return deleted_count

    def _update_playlist_membership(
        self,
        playlist_id: str,
        playlist_name: str,
        api_tracks: list[Track],
        library: Library,
    ) -> None:
        """Update library to reflect current playlist membership from API."""
        api_track_ids = {t.id for t in api_tracks}

        # Update playlist metadata
        library.update_playlist(playlist_id, playlist_name, len(api_tracks))

        # Add playlist to tracks that are in API response and already downloaded
        for track in api_tracks:
            if library.is_downloaded(track.id):
                library.add_track_to_playlist(track.id, playlist_id)

        # Remove playlist from tracks no longer in API response
        for lib_track in library.get_tracks_for_playlist(playlist_id):
            if lib_track.id not in api_track_ids:
                library.remove_track_from_playlist(lib_track.id, playlist_id)

    async def run(
        self,
        sync_spotify: bool = True,
        sync_youtube: bool = True,
    ) -> SyncResult:
        """Run sync for selected sources."""
        playlist_results: list[PlaylistResult] = []
        global_error: str | None = None

        notifier = Notifier(
            ntfy_server=self.config.notifications.ntfy_server,
            ntfy_topic=self.config.notifications.ntfy_topic,
            notify_on_success=self.config.notifications.notify_on_success,
            notify_on_failure=self.config.notifications.notify_on_failure,
        )

        try:
            if sync_spotify and self.config.spotify.enabled:
                spotify_results = await self._sync_spotify()
                playlist_results.extend(spotify_results)

            if sync_youtube and self.config.youtube.enabled:
                youtube_results = await self._sync_youtube()
                playlist_results.extend(youtube_results)

        except Exception as e:
            global_error = str(e)
            logger.exception("Sync failed with error")

        result = SyncResult(
            playlists=playlist_results,
            transferred=False,
            global_error=global_error,
        )

        notifier.send(result)
        return result

    async def _sync_spotify(self) -> list[PlaylistResult]:
        """Sync Spotify playlists using browser recording."""
        playlist_results: list[PlaylistResult] = []

        if not self.config.spotify.playlists:
            logger.info("No Spotify playlists configured")
            return playlist_results

        api = SpotifyAPI(
            client_id=self.config.spotify.client_id,
            client_secret=self.config.spotify.client_secret,
        )

        # Fetch all playlist tracks from API
        logger.info("Fetching Spotify playlist data...")
        all_playlist_tracks = self._fetch_spotify_playlists(api)

        # Determine which playlists have new tracks
        playlists_with_new_tracks: dict[str, list[Track]] = {}
        for playlist in self.config.spotify.playlists:
            all_tracks = all_playlist_tracks.get(playlist.playlist_id, [])
            new_tracks = self._filter_new_tracks(all_tracks, self.spotify_library)
            if new_tracks:
                playlists_with_new_tracks[playlist.playlist_id] = new_tracks
                logger.info(
                    f"Spotify '{playlist.name}': {len(new_tracks)} new tracks "
                    f"(of {len(all_tracks)} total)"
                )
            else:
                logger.info(
                    f"Spotify '{playlist.name}': fully synced ({len(all_tracks)} tracks)"
                )

        # Download new tracks if any exist
        if playlists_with_new_tracks:
            total_new = sum(len(tracks) for tracks in playlists_with_new_tracks.values())
            logger.info(
                f"Found {total_new} new Spotify tracks. Starting recording..."
            )

            try:
                with AudioRecorder(bitrate=self.config.audio.bitrate) as recorder:
                    async with SpotifyBrowser(
                        cookies_dir=self.config.paths.music_dir.parent / "cookies",
                        audio_sink=recorder.sink_name,
                    ) as browser:
                        if not await browser.is_logged_in():
                            raise RuntimeError("Login expired - please re-authenticate")

                        for playlist in self.config.spotify.playlists:
                            new_tracks = playlists_with_new_tracks.get(playlist.playlist_id)
                            all_tracks = all_playlist_tracks.get(playlist.playlist_id, [])
                            if new_tracks:
                                result = await self._sync_spotify_playlist_tracks(
                                    playlist, new_tracks, all_tracks, browser, recorder
                                )
                            else:
                                result = PlaylistResult(
                                    name=playlist.name, tracks_synced=0, error=None
                                )
                            playlist_results.append(result)

            except RuntimeError as e:
                for playlist in self.config.spotify.playlists:
                    if not any(r.name == playlist.name for r in playlist_results):
                        playlist_results.append(
                            PlaylistResult(name=playlist.name, tracks_synced=0, error=str(e))
                        )
        else:
            logger.info("All Spotify playlists are fully synced.")
            for playlist in self.config.spotify.playlists:
                playlist_results.append(
                    PlaylistResult(name=playlist.name, tracks_synced=0, error=None)
                )

        # Update playlist membership for all playlists
        logger.info("Updating Spotify playlist membership...")
        for playlist in self.config.spotify.playlists:
            all_tracks = all_playlist_tracks.get(playlist.playlist_id, [])
            self._update_playlist_membership(
                playlist.playlist_id, playlist.name, all_tracks, self.spotify_library
            )

        # Cleanup orphaned tracks
        orphans_deleted = self._cleanup_orphaned_tracks(
            self.spotify_library, self.spotify_music_dir
        )
        if orphans_deleted > 0:
            logger.info(f"Cleaned up {orphans_deleted} orphaned Spotify tracks")

        return playlist_results

    def _fetch_spotify_playlists(self, api: SpotifyAPI) -> dict[str, list[Track]]:
        """Fetch all tracks for all Spotify playlists."""
        all_playlist_tracks: dict[str, list[Track]] = {}

        for playlist in self.config.spotify.playlists:
            try:
                tracks = api.get_playlist_tracks(playlist.playlist_id)
                all_playlist_tracks[playlist.playlist_id] = tracks
                logger.debug(f"Fetched {len(tracks)} tracks from '{playlist.name}'")
            except Exception as e:
                logger.error(f"Failed to fetch playlist '{playlist.name}': {e}")
                all_playlist_tracks[playlist.playlist_id] = []

        return all_playlist_tracks

    async def _sync_spotify_playlist_tracks(
        self,
        playlist: PlaylistConfig,
        new_tracks: list[Track],
        all_tracks: list[Track],
        browser: "SpotifyBrowser",
        recorder: "AudioRecorder",
    ) -> PlaylistResult:
        """Sync tracks for a Spotify playlist using appropriate playback mode."""
        try:
            mode = self._select_playback_mode(len(new_tracks), len(all_tracks))
            logger.info(
                f"Spotify '{playlist.name}': {len(new_tracks)} new of {len(all_tracks)} "
                f"total, using {mode} mode"
            )

            if mode == "playlist":
                new_track_ids = {t.id for t in new_tracks}
                synced_count = await self._record_playlist_mode(
                    playlist.playlist_id,
                    all_tracks,
                    new_track_ids,
                    browser,
                    recorder,
                )
            else:
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

    async def _sync_youtube(self) -> list[PlaylistResult]:
        """Sync YouTube playlists using yt-dlp."""
        playlist_results: list[PlaylistResult] = []

        if not self.config.youtube.playlists:
            logger.info("No YouTube playlists configured")
            return playlist_results

        downloader = YouTubeDownloader(
            output_dir=self.youtube_music_dir,
            bitrate=self.config.audio.bitrate,
        )

        for playlist in self.config.youtube.playlists:
            try:
                logger.info(f"Fetching YouTube playlist: {playlist.name}")
                all_tracks = downloader.get_playlist_tracks(
                    playlist.url, playlist.name
                )

                new_tracks = self._filter_new_tracks(all_tracks, self.youtube_library)

                if new_tracks:
                    logger.info(
                        f"YouTube '{playlist.name}': {len(new_tracks)} new tracks "
                        f"(of {len(all_tracks)} total)"
                    )

                    downloaded = downloader.download_tracks(new_tracks)

                    # Add downloaded tracks to library
                    for track in new_tracks[:downloaded]:
                        self.youtube_library.add_track(
                            track.id,
                            f"{track.id}.mp3",
                            track.name,
                            track.artist_string,
                            playlist.playlist_id,
                        )

                    playlist_results.append(
                        PlaylistResult(
                            name=playlist.name,
                            tracks_synced=downloaded,
                            error=None,
                        )
                    )
                else:
                    logger.info(
                        f"YouTube '{playlist.name}': fully synced ({len(all_tracks)} tracks)"
                    )
                    playlist_results.append(
                        PlaylistResult(name=playlist.name, tracks_synced=0, error=None)
                    )

                # Update playlist membership
                self._update_playlist_membership(
                    playlist.playlist_id, playlist.name, all_tracks, self.youtube_library
                )

            except Exception as e:
                logger.error(f"Failed to sync YouTube playlist '{playlist.name}': {e}")
                playlist_results.append(
                    PlaylistResult(name=playlist.name, tracks_synced=0, error=str(e))
                )

        # Cleanup orphaned tracks
        orphans_deleted = self._cleanup_orphaned_tracks(
            self.youtube_library, self.youtube_music_dir
        )
        if orphans_deleted > 0:
            logger.info(f"Cleaned up {orphans_deleted} orphaned YouTube tracks")

        return playlist_results

    async def _record_track(
        self,
        track: Track,
        browser: "SpotifyBrowser",
        recorder: "AudioRecorder",
    ) -> None:
        output_path = self.spotify_music_dir / f"{track.id}.mp3"

        logger.info(f"Recording: {track.name} by {track.artist_string}")

        await browser.play_track(track.id)
        await asyncio.sleep(2)

        recorder.start_recording(output_path)
        await asyncio.sleep(track.duration_seconds + 2)
        recorder.stop_recording()

        await browser.pause()

        tag_mp3(output_path, track)
        # Note: playlist_id will be added by _update_playlist_membership
        self.spotify_library.add_track(
            track.id, f"{track.id}.mp3", track.name, track.artist_string, ""
        )

        logger.info(f"Completed: {track.name}")

    async def _record_playlist_mode(
        self,
        playlist_id: str,
        all_tracks: list[Track],
        new_track_ids: set[str],
        browser: "SpotifyBrowser",
        recorder: "AudioRecorder",
    ) -> int:
        """Record tracks by playing the playlist. Returns count of tracks recorded."""
        track_map = {t.id: t for t in all_tracks}
        recorded_count = 0

        logger.info(
            f"Starting playlist mode for {len(all_tracks)} tracks "
            f"({len(new_track_ids)} new)"
        )

        # Start playing the playlist
        await browser.play_playlist(playlist_id)
        await asyncio.sleep(2)

        current_track_id = browser.get_current_track_id()
        tracks_seen: set[str] = set()

        while current_track_id and len(tracks_seen) < len(all_tracks):
            tracks_seen.add(current_track_id)
            track = track_map.get(current_track_id)

            if not track:
                logger.warning(f"Unknown track playing: {current_track_id}")
            elif current_track_id in new_track_ids:
                # Record this track
                logger.info(f"Recording: {track.name} by {track.artist_string}")
                try:
                    await self._record_current_track(track, browser, recorder)
                    recorded_count += 1
                except Exception as e:
                    logger.error(f"Failed to record {track.name}: {e}")
            else:
                # Let existing track play through
                logger.debug(f"Skipping (already have): {track.name}")

            # Wait for next track
            timeout = (track.duration_seconds + 30) if track else 300
            next_track_id = await browser.wait_for_track_change(
                current_track_id,
                timeout_seconds=timeout
            )

            if next_track_id is None:
                logger.info("Playlist finished or timed out")
                break

            current_track_id = next_track_id

        return recorded_count

    async def _record_current_track(
        self,
        track: Track,
        browser: "SpotifyBrowser",
        recorder: "AudioRecorder",
    ) -> None:
        """Record the currently playing track."""
        output_path = self.spotify_music_dir / f"{track.id}.mp3"

        recorder.start_recording(output_path)
        await asyncio.sleep(track.duration_seconds + 2)
        recorder.stop_recording()

        tag_mp3(output_path, track)
        self.spotify_library.add_track(
            track.id, f"{track.id}.mp3", track.name, track.artist_string, ""
        )

        logger.info(f"Completed: {track.name}")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_orchestrator_sources.py -v`
Expected: All tests pass

**Step 5: Run all tests**

Run: `pytest -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add spotify_swimmer/orchestrator.py tests/test_orchestrator_sources.py
git commit -m "feat: update orchestrator for multi-source support"
```

---

## Task 7: Update Transfer for Multi-Source Support

**Files:**
- Modify: `spotify_swimmer/transfer.py`
- Test: `tests/test_transfer.py`

**Step 1: Write the failing tests**

Create `tests/test_transfer_sources.py`:

```python
# tests/test_transfer_sources.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from spotify_swimmer.library import Library
from spotify_swimmer.transfer import InteractiveTransfer


class TestMultiSourceTransfer:
    @pytest.fixture
    def setup_multi_source(self, tmp_path: Path):
        """Setup multi-source test environment."""
        # Create directory structure
        spotify_dir = tmp_path / "spotify"
        youtube_dir = tmp_path / "youtube"
        spotify_music = spotify_dir / "music"
        youtube_music = youtube_dir / "music"
        headphones = tmp_path / "headphones" / "Music"

        spotify_music.mkdir(parents=True)
        youtube_music.mkdir(parents=True)
        headphones.mkdir(parents=True)

        # Create libraries
        spotify_lib = Library(spotify_dir / "library.json")
        youtube_lib = Library(youtube_dir / "library.json")

        # Add tracks
        spotify_lib.add_track("sp1", "sp1.mp3", "Spotify Song", "Artist", "playlist1")
        spotify_lib.update_playlist("playlist1", "Spotify Playlist", 1)
        (spotify_music / "sp1.mp3").write_bytes(b"spotify data")

        youtube_lib.add_track("yt1", "yt1.mp3", "YouTube Video", "Channel", "ytplaylist")
        youtube_lib.update_playlist("ytplaylist", "YouTube Playlist", 1)
        (youtube_music / "yt1.mp3").write_bytes(b"youtube data")

        # Config mock
        config = MagicMock()
        config.paths.music_dir = tmp_path
        config.paths.headphones_mount = tmp_path / "headphones"
        config.paths.headphones_music_folder = "Music"

        return config, spotify_lib, youtube_lib, headphones

    def test_transfer_both_sources(self, setup_multi_source):
        config, spotify_lib, youtube_lib, headphones = setup_multi_source

        transfer = InteractiveTransfer(
            config,
            sources=None,  # Both sources
            spotify_library=spotify_lib,
            youtube_library=youtube_lib,
        )

        status = transfer.compute_status()

        assert status.local_track_count == 2
        assert status.new_to_transfer == 2

    def test_transfer_spotify_only(self, setup_multi_source):
        config, spotify_lib, youtube_lib, headphones = setup_multi_source

        transfer = InteractiveTransfer(
            config,
            sources=["spotify"],
            spotify_library=spotify_lib,
            youtube_library=youtube_lib,
        )

        status = transfer.compute_status()

        assert status.local_track_count == 1
        assert status.new_to_transfer == 1

    def test_transfer_youtube_only(self, setup_multi_source):
        config, spotify_lib, youtube_lib, headphones = setup_multi_source

        transfer = InteractiveTransfer(
            config,
            sources=["youtube"],
            spotify_library=spotify_lib,
            youtube_library=youtube_lib,
        )

        status = transfer.compute_status()

        assert status.local_track_count == 1
        assert status.new_to_transfer == 1

    def test_sync_copies_from_both_sources(self, setup_multi_source):
        config, spotify_lib, youtube_lib, headphones = setup_multi_source

        transfer = InteractiveTransfer(
            config,
            sources=None,
            spotify_library=spotify_lib,
            youtube_library=youtube_lib,
        )

        copied, removed = transfer.sync_changes()

        assert copied == 2
        assert (headphones / "sp1.mp3").exists()
        assert (headphones / "yt1.mp3").exists()

    def test_sync_copies_from_spotify_only(self, setup_multi_source):
        config, spotify_lib, youtube_lib, headphones = setup_multi_source

        transfer = InteractiveTransfer(
            config,
            sources=["spotify"],
            spotify_library=spotify_lib,
            youtube_library=youtube_lib,
        )

        copied, removed = transfer.sync_changes()

        assert copied == 1
        assert (headphones / "sp1.mp3").exists()
        assert not (headphones / "yt1.mp3").exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_transfer_sources.py -v`
Expected: FAIL with TypeError about 'sources' argument

**Step 3: Update transfer.py for multi-source support**

Update `spotify_swimmer/transfer.py`:

```python
# spotify_swimmer/transfer.py
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from spotify_swimmer.library import Library


@dataclass
class PlaylistStatus:
    name: str
    total_tracks: int
    new_tracks: int
    source: str = "spotify"
    track_details: list[tuple[str, str, str]] = field(default_factory=list)
    # track_details: (track_id, title - artist, status: "synced"/"new")


@dataclass
class TransferStatus:
    local_track_count: int
    headphones_track_count: int
    new_to_transfer: int
    orphaned_on_headphones: int
    playlists: list[PlaylistStatus] = field(default_factory=list)
    orphaned_files: list[str] = field(default_factory=list)


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


class InteractiveTransfer:
    def __init__(
        self,
        config,
        sources: list[str] | None = None,
        spotify_library: Library | None = None,
        youtube_library: Library | None = None,
    ):
        self.config = config
        self.sources = sources or ["spotify", "youtube"]

        # Setup libraries
        spotify_base = config.paths.music_dir / "spotify"
        youtube_base = config.paths.music_dir / "youtube"

        self.spotify_library = spotify_library or Library(spotify_base / "library.json")
        self.youtube_library = youtube_library or Library(youtube_base / "library.json")

        self.spotify_music_dir = spotify_base / "music"
        self.youtube_music_dir = youtube_base / "music"

        self.headphones_path = (
            config.paths.headphones_mount / config.paths.headphones_music_folder
        )

    def is_mounted(self) -> bool:
        return (
            self.config.paths.headphones_mount.exists()
            and self.headphones_path.exists()
        )

    def _get_headphones_files(self) -> set[str]:
        """Get set of MP3 filenames on headphones."""
        if not self.headphones_path.exists():
            return set()
        return {f.name for f in self.headphones_path.glob("*.mp3")}

    def _get_local_files(self) -> dict[str, Path]:
        """Get dict of MP3 filenames to paths from selected sources."""
        files = {}
        if "spotify" in self.sources and self.spotify_music_dir.exists():
            for f in self.spotify_music_dir.glob("*.mp3"):
                files[f.name] = f
        if "youtube" in self.sources and self.youtube_music_dir.exists():
            for f in self.youtube_music_dir.glob("*.mp3"):
                files[f.name] = f
        return files

    def _get_local_filenames(self) -> set[str]:
        """Get set of MP3 filenames from selected source libraries."""
        filenames = set()
        if "spotify" in self.sources:
            filenames.update(t.filename for t in self.spotify_library.get_all_tracks())
        if "youtube" in self.sources:
            filenames.update(t.filename for t in self.youtube_library.get_all_tracks())
        return filenames

    def compute_status(self) -> TransferStatus:
        """Compute current transfer status."""
        local_files = self._get_local_filenames()
        headphones_files = self._get_headphones_files()

        new_to_transfer = local_files - headphones_files
        orphaned_on_headphones = headphones_files - local_files

        # Build playlist status
        playlists = []

        if "spotify" in self.sources:
            for playlist in self.spotify_library.get_all_playlists():
                tracks = self.spotify_library.get_tracks_for_playlist(playlist.id)
                details = []
                new_count = 0

                for track in tracks:
                    if track.filename in headphones_files:
                        status = "synced"
                    else:
                        status = "new"
                        new_count += 1
                    details.append(
                        (track.id, f"{track.title} - {track.artist}", status)
                    )

                playlists.append(
                    PlaylistStatus(
                        name=playlist.name,
                        total_tracks=len(tracks),
                        new_tracks=new_count,
                        source="spotify",
                        track_details=details,
                    )
                )

        if "youtube" in self.sources:
            for playlist in self.youtube_library.get_all_playlists():
                tracks = self.youtube_library.get_tracks_for_playlist(playlist.id)
                details = []
                new_count = 0

                for track in tracks:
                    if track.filename in headphones_files:
                        status = "synced"
                    else:
                        status = "new"
                        new_count += 1
                    details.append(
                        (track.id, f"{track.title} - {track.artist}", status)
                    )

                playlists.append(
                    PlaylistStatus(
                        name=playlist.name,
                        total_tracks=len(tracks),
                        new_tracks=new_count,
                        source="youtube",
                        track_details=details,
                    )
                )

        return TransferStatus(
            local_track_count=len(local_files),
            headphones_track_count=len(headphones_files),
            new_to_transfer=len(new_to_transfer),
            orphaned_on_headphones=len(orphaned_on_headphones),
            playlists=playlists,
            orphaned_files=list(orphaned_on_headphones),
        )

    def sync_changes(self) -> tuple[int, int]:
        """Sync changes to headphones: copy new files, remove orphans.

        Returns tuple of (files_copied, files_removed).
        """
        if not self.is_mounted():
            raise RuntimeError(
                f"Headphones not mounted at {self.config.paths.headphones_mount}"
            )

        local_files = self._get_local_files()
        local_filenames = set(local_files.keys())
        headphones_files = self._get_headphones_files()

        new_to_transfer = local_filenames - headphones_files
        orphaned_on_headphones = headphones_files - local_filenames

        # Copy new files
        files_copied = 0
        for filename in new_to_transfer:
            src = local_files.get(filename)
            if src and src.exists():
                dst = self.headphones_path / filename
                shutil.copy2(src, dst)
                files_copied += 1

        # Remove orphans
        files_removed = 0
        for filename in orphaned_on_headphones:
            orphan_path = self.headphones_path / filename
            if orphan_path.exists():
                orphan_path.unlink()
                files_removed += 1

        return files_copied, files_removed

    def full_reset(self) -> int:
        """Delete all files on headphones and copy all library tracks.

        Returns count of files copied.
        """
        if not self.is_mounted():
            raise RuntimeError(
                f"Headphones not mounted at {self.config.paths.headphones_mount}"
            )

        # Delete all MP3s on headphones
        for mp3_file in self.headphones_path.glob("*.mp3"):
            mp3_file.unlink()

        # Copy all library tracks from selected sources
        local_files = self._get_local_files()
        files_copied = 0

        for filename, src in local_files.items():
            if src.exists():
                dst = self.headphones_path / filename
                shutil.copy2(src, dst)
                files_copied += 1

        return files_copied

    def run(self) -> int:
        """Run the interactive transfer menu. Returns exit code."""
        import logging

        logger = logging.getLogger(__name__)

        if not self.is_mounted():
            logger.error(
                f"Headphones not mounted at {self.config.paths.headphones_mount}"
            )
            print(
                f"\nHeadphones not mounted at {self.config.paths.headphones_mount}"
            )
            print("Please connect your headphones and try again.")
            return 1

        status = self.compute_status()

        # Display status
        source_label = " + ".join(s.capitalize() for s in self.sources)
        print(f"\n=== Transfer Status ({source_label}) ===")
        print(f"Local library: {status.local_track_count} tracks")
        print(f"On headphones: {status.headphones_track_count} tracks")
        print(f"New to transfer: {status.new_to_transfer}")
        print(f"Orphaned on headphones: {status.orphaned_on_headphones}")

        if status.playlists:
            print("\n--- Playlists ---")
            for playlist in status.playlists:
                synced = playlist.total_tracks - playlist.new_tracks
                source_tag = f"[{playlist.source[:2].upper()}]"
                print(
                    f"  {source_tag} {playlist.name}: "
                    f"{synced}/{playlist.total_tracks} synced"
                )

        if status.orphaned_files:
            print("\n--- Orphaned files ---")
            for filename in status.orphaned_files[:5]:
                print(f"  {filename}")
            if len(status.orphaned_files) > 5:
                print(f"  ... and {len(status.orphaned_files) - 5} more")

        # Show menu
        print("\n=== Options ===")
        print("[1] Sync changes (copy new, remove orphans)")
        print("[2] Full reset (delete all, copy fresh)")
        print("[3] View detailed status")
        print("[q] Quit")

        choice = input("\nSelect option: ").strip().lower()

        if choice == "1":
            copied, removed = self.sync_changes()
            print(f"\nSynced: {copied} copied, {removed} removed")
        elif choice == "2":
            confirm = input("This will delete ALL files on headphones. Continue? [y/N]: ")
            if confirm.lower() == "y":
                copied = self.full_reset()
                print(f"\nReset complete: {copied} files copied")
            else:
                print("Cancelled")
        elif choice == "3":
            self._show_detailed_status(status)
        elif choice == "q":
            print("Goodbye!")
        else:
            print("Invalid option")

        return 0

    def _show_detailed_status(self, status: TransferStatus) -> None:
        """Display detailed status by playlist."""
        print("\n=== Detailed Status ===")
        for playlist in status.playlists:
            source_tag = f"[{playlist.source[:2].upper()}]"
            print(f"\n{source_tag} {playlist.name}:")
            for track_id, title, track_status in playlist.track_details:
                marker = "✓" if track_status == "synced" else "○"
                print(f"  {marker} {title}")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_transfer_sources.py -v`
Expected: All tests pass

**Step 5: Update existing integration tests**

Update `tests/test_integration.py` fixture to use new config structure:

```python
# tests/test_integration.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from spotify_swimmer.library import Library
from spotify_swimmer.transfer import InteractiveTransfer


class TestFullWorkflow:
    @pytest.fixture
    def setup_environment(self, tmp_path: Path):
        """Setup complete test environment."""
        # Create multi-source directory structure
        spotify_music = tmp_path / "spotify" / "music"
        youtube_music = tmp_path / "youtube" / "music"
        spotify_music.mkdir(parents=True)
        youtube_music.mkdir(parents=True)

        headphones = tmp_path / "headphones" / "Music"
        headphones.mkdir(parents=True)

        config = MagicMock()
        config.paths.music_dir = tmp_path
        config.paths.headphones_mount = tmp_path / "headphones"
        config.paths.headphones_music_folder = "Music"
        config.spotify.client_id = "test"
        config.spotify.client_secret = "test"
        config.spotify.enabled = True
        config.spotify.playlists = []
        config.youtube.enabled = False
        config.youtube.playlists = []
        config.audio.bitrate = 192
        config.behavior.skip_existing = True
        config.notifications.ntfy_server = "https://ntfy.sh"
        config.notifications.ntfy_topic = "test"
        config.notifications.notify_on_success = False
        config.notifications.notify_on_failure = False

        return config, tmp_path

    def test_library_tracks_playlist_membership(self, setup_environment):
        config, tmp_path = setup_environment

        lib = Library(tmp_path / "library.json")

        # Add track to playlist1
        lib.add_track("track1", "track1.mp3", "Song", "Artist", "playlist1")
        assert lib.get_track("track1").playlists == ["playlist1"]

        # Add same track to playlist2
        lib.add_track_to_playlist("track1", "playlist2")
        assert set(lib.get_track("track1").playlists) == {"playlist1", "playlist2"}

        # Remove from playlist1
        lib.remove_track_from_playlist("track1", "playlist1")
        assert lib.get_track("track1").playlists == ["playlist2"]
        assert not lib.get_track("track1").is_orphaned

        # Remove from playlist2 - now orphaned
        lib.remove_track_from_playlist("track1", "playlist2")
        assert lib.get_track("track1").is_orphaned

    def test_transfer_syncs_correctly(self, setup_environment):
        config, tmp_path = setup_environment

        # Setup spotify library
        spotify_lib = Library(tmp_path / "spotify" / "library.json")
        spotify_lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        spotify_lib.add_track("track2", "track2.mp3", "Song 2", "Artist", "playlist1")
        spotify_lib.update_playlist("playlist1", "Test Playlist", 2)

        # Create local files in spotify music dir
        spotify_music = tmp_path / "spotify" / "music"
        (spotify_music / "track1.mp3").write_bytes(b"data1")
        (spotify_music / "track2.mp3").write_bytes(b"data2")

        # Create orphan on headphones
        headphones = config.paths.headphones_mount / "Music"
        (headphones / "orphan.mp3").write_bytes(b"orphan")

        transfer = InteractiveTransfer(
            config,
            sources=["spotify"],
            spotify_library=spotify_lib,
        )
        status = transfer.compute_status()

        assert status.local_track_count == 2
        assert status.new_to_transfer == 2
        assert status.orphaned_on_headphones == 1

        added, removed = transfer.sync_changes()

        assert added == 2
        assert removed == 1
        assert (headphones / "track1.mp3").exists()
        assert (headphones / "track2.mp3").exists()
        assert not (headphones / "orphan.mp3").exists()

    def test_full_reset_clears_headphones(self, setup_environment):
        config, tmp_path = setup_environment

        spotify_lib = Library(tmp_path / "spotify" / "library.json")
        spotify_lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")

        # Create local file
        spotify_music = tmp_path / "spotify" / "music"
        (spotify_music / "track1.mp3").write_bytes(b"data1")

        # Put old files on headphones
        headphones = config.paths.headphones_mount / "Music"
        (headphones / "old1.mp3").write_bytes(b"old1")
        (headphones / "old2.mp3").write_bytes(b"old2")

        transfer = InteractiveTransfer(
            config,
            sources=["spotify"],
            spotify_library=spotify_lib,
        )
        copied = transfer.full_reset()

        assert copied == 1
        assert (headphones / "track1.mp3").exists()
        assert not (headphones / "old1.mp3").exists()
        assert not (headphones / "old2.mp3").exists()

    def test_playback_mode_selection(self):
        from spotify_swimmer.orchestrator import Orchestrator

        # 100% new -> playlist mode
        assert Orchestrator._select_playback_mode(10, 10) == "playlist"

        # 70% new -> playlist mode (at threshold)
        assert Orchestrator._select_playback_mode(7, 10) == "playlist"

        # 60% new -> individual mode
        assert Orchestrator._select_playback_mode(6, 10) == "individual"

        # 0% new -> individual mode
        assert Orchestrator._select_playback_mode(0, 10) == "individual"

        # Empty playlist -> individual mode
        assert Orchestrator._select_playback_mode(0, 0) == "individual"

    def test_library_persistence(self, setup_environment):
        config, tmp_path = setup_environment
        lib_path = tmp_path / "library.json"

        # Create library with data
        lib1 = Library(lib_path)
        lib1.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        lib1.add_track("track2", "track2.mp3", "Song 2", "Artist", "playlist1")
        lib1.update_playlist("playlist1", "My Playlist", 2)

        # Load in new instance
        lib2 = Library(lib_path)
        assert lib2.is_downloaded("track1")
        assert lib2.is_downloaded("track2")
        assert lib2.get_track("track1").title == "Song 1"

        playlist = lib2.get_playlist("playlist1")
        assert playlist is not None
        assert playlist.name == "My Playlist"
        assert playlist.track_count == 2
```

**Step 6: Run all tests to verify they pass**

Run: `pytest -v`
Expected: All tests pass

**Step 7: Commit**

```bash
git add spotify_swimmer/transfer.py tests/test_transfer_sources.py tests/test_integration.py
git commit -m "feat: update transfer for multi-source support"
```

---

## Task 8: Update Sample Config and Documentation

**Files:**
- Modify: `scripts/install-systemd.sh`
- Modify: `README.md`

**Step 1: Update sample config in install script**

Update `scripts/install-systemd.sh` sample config:

```bash
# Find the sample config section and replace with:
if [ ! -f "$INSTALL_DIR/config.yaml" ]; then
    cat > "$INSTALL_DIR/config.yaml" << 'EOF'
spotify:
  enabled: true
  client_id: "YOUR_SPOTIFY_CLIENT_ID"
  client_secret: "YOUR_SPOTIFY_CLIENT_SECRET"
  username: "YOUR_SPOTIFY_USERNAME"
  playlists:
    - name: "Discover Weekly"
      url: "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID"

youtube:
  enabled: false
  playlists:
    - name: "Coding Music"
      url: "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"

audio:
  bitrate: 192
  format: "mp3"

paths:
  music_dir: "~/.spotify-swimmer"
  headphones_mount: "/media/YOUR_USERNAME/HEADPHONES"
  headphones_music_folder: "Music"

notifications:
  ntfy_topic: "your-secret-topic"
  ntfy_server: "https://ntfy.sh"
  notify_on_success: false
  notify_on_failure: true

behavior:
  skip_existing: true
  trim_silence: true
EOF
    echo "Created sample config at $INSTALL_DIR/config.yaml"
    echo "Please edit it with your Spotify credentials and settings."
fi
```

**Step 2: Update README.md with YouTube documentation**

Update `README.md` to include YouTube support. Add new section and update existing sections.

**Step 3: Commit**

```bash
git add scripts/install-systemd.sh README.md
git commit -m "docs: update config and README for YouTube support"
```

---

## Task 9: Run Full Test Suite and Final Verification

**Step 1: Run the full test suite**

Run: `pytest -v`
Expected: All tests pass

**Step 2: Run type checking if available**

Run: `python -m mypy spotify_swimmer/` (if mypy is installed)
Expected: No type errors

**Step 3: Test manual CLI invocation**

Run: `spotify-swimmer --help`
Expected: Shows updated help with sync/transfer commands

Run: `spotify-swimmer sync --help`
Expected: Shows --spotify and --youtube flags

Run: `spotify-swimmer transfer --help`
Expected: Shows --spotify and --youtube flags

**Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final cleanup for YouTube support"
```

---

## Summary

This implementation plan adds YouTube playlist support through the following changes:

1. **Dependencies**: Add yt-dlp for YouTube downloads
2. **Track**: Add `source` field to distinguish Spotify vs YouTube tracks
3. **Config**: Restructure to support `spotify.playlists` and `youtube.playlists`
4. **YouTube Downloader**: New module using yt-dlp with rate limiting
5. **CLI**: Add `--spotify`/`--youtube` flags to both commands
6. **Orchestrator**: Handle both sources with separate libraries
7. **Transfer**: Merge sources for flat transfer to headphones
8. **Documentation**: Update README and sample config

The implementation maintains backward compatibility with existing configs by auto-migrating root-level playlists to `spotify.playlists`.
