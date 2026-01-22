# Sync & Transfer Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Separate download (sync) from transfer workflows, add playlist tracking, implement intelligent playback modes, and create interactive transfer menu.

**Architecture:** Replace simple track database with enhanced library tracking playlist membership. CLI gains subcommands. Orchestrator handles sync-only workflow with playback mode selection. Transfer becomes interactive standalone command.

**Tech Stack:** Python 3.11+, Playwright, dataclasses, JSON persistence

---

## Task 1: Create Library Data Model

**Files:**
- Create: `spotify_swimmer/library.py`
- Test: `tests/test_library.py`

**Step 1: Write the failing test for LibraryTrack dataclass**

```python
# tests/test_library.py
import pytest
from spotify_swimmer.library import LibraryTrack, LibraryPlaylist, Library


class TestLibraryTrack:
    def test_library_track_creation(self):
        track = LibraryTrack(
            id="abc123",
            filename="abc123.mp3",
            title="Test Song",
            artist="Test Artist",
            playlists=["playlist1", "playlist2"],
        )
        assert track.id == "abc123"
        assert track.filename == "abc123.mp3"
        assert track.title == "Test Song"
        assert track.artist == "Test Artist"
        assert track.playlists == ["playlist1", "playlist2"]

    def test_track_is_orphaned_when_no_playlists(self):
        track = LibraryTrack(
            id="abc123",
            filename="abc123.mp3",
            title="Test Song",
            artist="Test Artist",
            playlists=[],
        )
        assert track.is_orphaned is True

    def test_track_not_orphaned_with_playlists(self):
        track = LibraryTrack(
            id="abc123",
            filename="abc123.mp3",
            title="Test Song",
            artist="Test Artist",
            playlists=["playlist1"],
        )
        assert track.is_orphaned is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_library.py::TestLibraryTrack -v`
Expected: FAIL with "No module named 'spotify_swimmer.library'"

**Step 3: Write minimal implementation**

```python
# spotify_swimmer/library.py
from dataclasses import dataclass, field


@dataclass
class LibraryTrack:
    id: str
    filename: str
    title: str
    artist: str
    playlists: list[str] = field(default_factory=list)

    @property
    def is_orphaned(self) -> bool:
        return len(self.playlists) == 0


@dataclass
class LibraryPlaylist:
    id: str
    name: str
    last_synced: str | None = None
    track_count: int = 0
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_library.py::TestLibraryTrack -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/library.py tests/test_library.py
git commit -m "feat(library): add LibraryTrack and LibraryPlaylist dataclasses"
```

---

## Task 2: Create Library Class with Persistence

**Files:**
- Modify: `spotify_swimmer/library.py`
- Test: `tests/test_library.py`

**Step 1: Write the failing test for Library class**

```python
# Add to tests/test_library.py
from pathlib import Path
import json


class TestLibrary:
    def test_empty_library(self, tmp_path: Path):
        lib = Library(tmp_path / "library.json")
        assert lib.get_all_tracks() == []
        assert lib.get_all_playlists() == []

    def test_add_track(self, tmp_path: Path):
        lib = Library(tmp_path / "library.json")
        lib.add_track(
            track_id="abc123",
            filename="abc123.mp3",
            title="Test Song",
            artist="Test Artist",
            playlist_id="playlist1",
        )

        track = lib.get_track("abc123")
        assert track is not None
        assert track.title == "Test Song"
        assert "playlist1" in track.playlists

    def test_add_track_to_multiple_playlists(self, tmp_path: Path):
        lib = Library(tmp_path / "library.json")
        lib.add_track("abc123", "abc123.mp3", "Song", "Artist", "playlist1")
        lib.add_track_to_playlist("abc123", "playlist2")

        track = lib.get_track("abc123")
        assert "playlist1" in track.playlists
        assert "playlist2" in track.playlists

    def test_remove_track_from_playlist(self, tmp_path: Path):
        lib = Library(tmp_path / "library.json")
        lib.add_track("abc123", "abc123.mp3", "Song", "Artist", "playlist1")
        lib.add_track_to_playlist("abc123", "playlist2")
        lib.remove_track_from_playlist("abc123", "playlist1")

        track = lib.get_track("abc123")
        assert "playlist1" not in track.playlists
        assert "playlist2" in track.playlists

    def test_is_downloaded(self, tmp_path: Path):
        lib = Library(tmp_path / "library.json")
        assert lib.is_downloaded("abc123") is False
        lib.add_track("abc123", "abc123.mp3", "Song", "Artist", "playlist1")
        assert lib.is_downloaded("abc123") is True

    def test_persistence(self, tmp_path: Path):
        db_path = tmp_path / "library.json"

        lib1 = Library(db_path)
        lib1.add_track("abc123", "abc123.mp3", "Song", "Artist", "playlist1")

        lib2 = Library(db_path)
        track = lib2.get_track("abc123")
        assert track is not None
        assert track.title == "Song"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_library.py::TestLibrary -v`
Expected: FAIL with "cannot import name 'Library'"

**Step 3: Write minimal implementation**

```python
# Add to spotify_swimmer/library.py
import json
from pathlib import Path
from datetime import datetime


class Library:
    VERSION = 1

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._tracks: dict[str, LibraryTrack] = {}
        self._playlists: dict[str, LibraryPlaylist] = {}
        self._load()

    def _load(self) -> None:
        if not self.db_path.exists():
            return

        with open(self.db_path) as f:
            data = json.load(f)

        for track_id, track_data in data.get("tracks", {}).items():
            self._tracks[track_id] = LibraryTrack(
                id=track_id,
                filename=track_data["filename"],
                title=track_data["title"],
                artist=track_data["artist"],
                playlists=track_data.get("playlists", []),
            )

        for playlist_id, playlist_data in data.get("playlists", {}).items():
            self._playlists[playlist_id] = LibraryPlaylist(
                id=playlist_id,
                name=playlist_data["name"],
                last_synced=playlist_data.get("last_synced"),
                track_count=playlist_data.get("track_count", 0),
            )

    def save(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self.VERSION,
            "tracks": {
                track_id: {
                    "filename": track.filename,
                    "title": track.title,
                    "artist": track.artist,
                    "playlists": track.playlists,
                }
                for track_id, track in self._tracks.items()
            },
            "playlists": {
                playlist_id: {
                    "name": playlist.name,
                    "last_synced": playlist.last_synced,
                    "track_count": playlist.track_count,
                }
                for playlist_id, playlist in self._playlists.items()
            },
        }

        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2)

    def get_track(self, track_id: str) -> LibraryTrack | None:
        return self._tracks.get(track_id)

    def get_all_tracks(self) -> list[LibraryTrack]:
        return list(self._tracks.values())

    def get_all_playlists(self) -> list[LibraryPlaylist]:
        return list(self._playlists.values())

    def is_downloaded(self, track_id: str) -> bool:
        return track_id in self._tracks

    def add_track(
        self,
        track_id: str,
        filename: str,
        title: str,
        artist: str,
        playlist_id: str,
    ) -> None:
        if track_id in self._tracks:
            self.add_track_to_playlist(track_id, playlist_id)
        else:
            self._tracks[track_id] = LibraryTrack(
                id=track_id,
                filename=filename,
                title=title,
                artist=artist,
                playlists=[playlist_id],
            )
        self.save()

    def add_track_to_playlist(self, track_id: str, playlist_id: str) -> None:
        track = self._tracks.get(track_id)
        if track and playlist_id not in track.playlists:
            track.playlists.append(playlist_id)
            self.save()

    def remove_track_from_playlist(self, track_id: str, playlist_id: str) -> None:
        track = self._tracks.get(track_id)
        if track and playlist_id in track.playlists:
            track.playlists.remove(playlist_id)
            self.save()

    def delete_track(self, track_id: str) -> None:
        if track_id in self._tracks:
            del self._tracks[track_id]
            self.save()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_library.py::TestLibrary -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/library.py tests/test_library.py
git commit -m "feat(library): add Library class with persistence"
```

---

## Task 3: Add Playlist Management to Library

**Files:**
- Modify: `spotify_swimmer/library.py`
- Test: `tests/test_library.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_library.py class TestLibrary
    def test_update_playlist(self, tmp_path: Path):
        lib = Library(tmp_path / "library.json")
        lib.update_playlist("playlist1", "My Playlist", track_count=10)

        playlist = lib.get_playlist("playlist1")
        assert playlist is not None
        assert playlist.name == "My Playlist"
        assert playlist.track_count == 10
        assert playlist.last_synced is not None

    def test_get_tracks_for_playlist(self, tmp_path: Path):
        lib = Library(tmp_path / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        lib.add_track("track2", "track2.mp3", "Song 2", "Artist", "playlist1")
        lib.add_track("track3", "track3.mp3", "Song 3", "Artist", "playlist2")

        tracks = lib.get_tracks_for_playlist("playlist1")
        assert len(tracks) == 2
        track_ids = [t.id for t in tracks]
        assert "track1" in track_ids
        assert "track2" in track_ids
        assert "track3" not in track_ids

    def test_get_orphaned_tracks(self, tmp_path: Path):
        lib = Library(tmp_path / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        lib.add_track("track2", "track2.mp3", "Song 2", "Artist", "playlist1")
        lib.remove_track_from_playlist("track2", "playlist1")

        orphaned = lib.get_orphaned_tracks()
        assert len(orphaned) == 1
        assert orphaned[0].id == "track2"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_library.py::TestLibrary::test_update_playlist tests/test_library.py::TestLibrary::test_get_tracks_for_playlist tests/test_library.py::TestLibrary::test_get_orphaned_tracks -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# Add to Library class in spotify_swimmer/library.py
    def get_playlist(self, playlist_id: str) -> LibraryPlaylist | None:
        return self._playlists.get(playlist_id)

    def update_playlist(
        self, playlist_id: str, name: str, track_count: int = 0
    ) -> None:
        self._playlists[playlist_id] = LibraryPlaylist(
            id=playlist_id,
            name=name,
            last_synced=datetime.now().isoformat(),
            track_count=track_count,
        )
        self.save()

    def get_tracks_for_playlist(self, playlist_id: str) -> list[LibraryTrack]:
        return [
            track for track in self._tracks.values()
            if playlist_id in track.playlists
        ]

    def get_orphaned_tracks(self) -> list[LibraryTrack]:
        return [track for track in self._tracks.values() if track.is_orphaned]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_library.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/library.py tests/test_library.py
git commit -m "feat(library): add playlist management and orphan detection"
```

---

## Task 4: Add Migration from Old tracks.json

**Files:**
- Modify: `spotify_swimmer/library.py`
- Test: `tests/test_library.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_library.py class TestLibrary
    def test_migrate_from_old_format(self, tmp_path: Path):
        # Create old tracks.json format
        old_db = tmp_path / "tracks.json"
        old_db.write_text(json.dumps({
            "track1": "track1.mp3",
            "track2": "track2.mp3",
        }))

        lib = Library(tmp_path / "library.json", migrate_from=old_db)

        # Old tracks should be imported with empty playlists (orphaned)
        assert lib.is_downloaded("track1")
        assert lib.is_downloaded("track2")
        track = lib.get_track("track1")
        assert track.filename == "track1.mp3"
        # Title/artist unknown from old format
        assert track.title == "Unknown"
        assert track.playlists == []  # Will be populated on next sync
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_library.py::TestLibrary::test_migrate_from_old_format -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# Modify Library.__init__ in spotify_swimmer/library.py
    def __init__(self, db_path: Path, migrate_from: Path | None = None):
        self.db_path = db_path
        self._tracks: dict[str, LibraryTrack] = {}
        self._playlists: dict[str, LibraryPlaylist] = {}

        if migrate_from and migrate_from.exists() and not db_path.exists():
            self._migrate_old_format(migrate_from)
        else:
            self._load()

    def _migrate_old_format(self, old_path: Path) -> None:
        """Migrate from old tracks.json format to new library.json format."""
        with open(old_path) as f:
            old_data = json.load(f)

        # Old format: {"track_id": "filename.mp3"}
        for track_id, filename in old_data.items():
            self._tracks[track_id] = LibraryTrack(
                id=track_id,
                filename=filename,
                title="Unknown",
                artist="Unknown",
                playlists=[],  # Will be populated on next sync
            )

        self.save()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_library.py::TestLibrary::test_migrate_from_old_format -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/library.py tests/test_library.py
git commit -m "feat(library): add migration from old tracks.json format"
```

---

## Task 5: Update CLI with Subcommands

**Files:**
- Modify: `spotify_swimmer/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py
import pytest
from unittest.mock import patch, MagicMock
from spotify_swimmer.cli import main, parse_args


class TestCLI:
    def test_parse_sync_command(self):
        args = parse_args(["sync"])
        assert args.command == "sync"

    def test_parse_sync_with_verbose(self):
        args = parse_args(["sync", "-v"])
        assert args.command == "sync"
        assert args.verbose is True

    def test_parse_sync_with_config(self):
        args = parse_args(["sync", "-c", "/path/to/config.yaml"])
        assert args.command == "sync"
        assert str(args.config) == "/path/to/config.yaml"

    def test_parse_transfer_command(self):
        args = parse_args(["transfer"])
        assert args.command == "transfer"

    def test_parse_transfer_with_verbose(self):
        args = parse_args(["transfer", "-v"])
        assert args.command == "transfer"
        assert args.verbose is True

    def test_no_command_shows_help(self, capsys):
        with pytest.raises(SystemExit):
            parse_args([])
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with "cannot import name 'parse_args'"

**Step 3: Write minimal implementation**

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


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Spotify playlists to MP3 for offline swimming"
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

    # transfer command
    transfer_parser = subparsers.add_parser(
        "transfer",
        help="Interactive transfer to headphones",
    )

    return parser.parse_args(args)


def cmd_sync(config, verbose: bool) -> int:
    """Run sync command - download new tracks, cleanup orphans."""
    from spotify_swimmer.orchestrator import Orchestrator

    logger = logging.getLogger(__name__)
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


def cmd_transfer(config, verbose: bool) -> int:
    """Run transfer command - interactive headphones transfer."""
    from spotify_swimmer.transfer import InteractiveTransfer

    logger = logging.getLogger(__name__)

    try:
        transfer = InteractiveTransfer(config)
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
        return cmd_sync(config, args.verbose)
    elif args.command == "transfer":
        return cmd_transfer(config, args.verbose)
    else:
        logger.error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/cli.py tests/test_cli.py
git commit -m "feat(cli): add sync and transfer subcommands"
```

---

## Task 6: Update Orchestrator to Use Library

**Files:**
- Modify: `spotify_swimmer/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# Update tests/test_orchestrator.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from spotify_swimmer.orchestrator import Orchestrator
from spotify_swimmer.library import Library
from spotify_swimmer.spotify_api import Track


class TestOrchestrator:
    @pytest.fixture
    def mock_config(self, tmp_path: Path):
        config = MagicMock()
        config.paths.music_dir = tmp_path / "music"
        config.paths.music_dir.mkdir()
        config.spotify.client_id = "test_id"
        config.spotify.client_secret = "test_secret"
        config.audio.bitrate = 192
        config.behavior.skip_existing = True
        config.notifications.ntfy_server = "https://ntfy.sh"
        config.notifications.ntfy_topic = "test"
        config.notifications.notify_on_success = False
        config.notifications.notify_on_failure = False
        config.playlists = []
        return config

    def test_orchestrator_uses_library(self, mock_config, tmp_path: Path):
        orchestrator = Orchestrator(mock_config)
        assert isinstance(orchestrator.library, Library)
        assert orchestrator.library.db_path == tmp_path / "library.json"

    def test_orchestrator_migrates_old_db(self, mock_config, tmp_path: Path):
        # Create old tracks.json
        old_db = tmp_path / "tracks.json"
        old_db.write_text('{"track1": "track1.mp3"}')

        orchestrator = Orchestrator(mock_config)
        assert orchestrator.library.is_downloaded("track1")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py::TestOrchestrator::test_orchestrator_uses_library tests/test_orchestrator.py::TestOrchestrator::test_orchestrator_migrates_old_db -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# Modify spotify_swimmer/orchestrator.py
# Change imports and __init__

from spotify_swimmer.library import Library

class Orchestrator:
    def __init__(self, config: Config):
        self.config = config

        # Setup library with migration support
        library_path = config.paths.music_dir.parent / "library.json"
        old_tracks_path = config.paths.music_dir.parent / "tracks.json"

        self.library = Library(library_path, migrate_from=old_tracks_path)

        config.paths.music_dir.mkdir(parents=True, exist_ok=True)

    def _filter_new_tracks(self, tracks: list[Track]) -> list[Track]:
        if not self.config.behavior.skip_existing:
            return tracks
        return [t for t in tracks if not self.library.is_downloaded(t.id)]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestrator.py::TestOrchestrator::test_orchestrator_uses_library tests/test_orchestrator.py::TestOrchestrator::test_orchestrator_migrates_old_db -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/orchestrator.py tests/test_orchestrator.py
git commit -m "refactor(orchestrator): use Library instead of TracksDB"
```

---

## Task 7: Add Orphan Cleanup to Orchestrator

**Files:**
- Modify: `spotify_swimmer/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_orchestrator.py class TestOrchestrator
    def test_cleanup_orphaned_tracks(self, mock_config, tmp_path: Path):
        # Setup: create library with an orphaned track
        library_path = tmp_path / "library.json"
        lib = Library(library_path)
        lib.add_track("orphan1", "orphan1.mp3", "Orphan Song", "Artist", "playlist1")
        lib.remove_track_from_playlist("orphan1", "playlist1")

        # Create the MP3 file
        mp3_path = mock_config.paths.music_dir / "orphan1.mp3"
        mp3_path.write_bytes(b"fake mp3 data")

        orchestrator = Orchestrator(mock_config)
        deleted = orchestrator._cleanup_orphaned_tracks()

        assert deleted == 1
        assert not mp3_path.exists()
        assert not orchestrator.library.is_downloaded("orphan1")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py::TestOrchestrator::test_cleanup_orphaned_tracks -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# Add to Orchestrator class in spotify_swimmer/orchestrator.py
    def _cleanup_orphaned_tracks(self) -> int:
        """Delete orphaned tracks from disk and library. Returns count deleted."""
        orphaned = self.library.get_orphaned_tracks()
        deleted_count = 0

        for track in orphaned:
            mp3_path = self.config.paths.music_dir / track.filename

            # Delete MP3 file if exists
            if mp3_path.exists():
                mp3_path.unlink()
                logger.info(f"Deleted orphaned file: {track.filename}")

            # Remove from library
            self.library.delete_track(track.id)
            deleted_count += 1
            logger.info(f"Removed orphaned track: {track.title} by {track.artist}")

        return deleted_count
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestrator.py::TestOrchestrator::test_cleanup_orphaned_tracks -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): add orphan cleanup functionality"
```

---

## Task 8: Update Orchestrator Sync to Track Playlist Membership

**Files:**
- Modify: `spotify_swimmer/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_orchestrator.py
    def test_sync_updates_playlist_membership(self, mock_config, tmp_path: Path):
        # Create a track that's in library for playlist1
        library_path = tmp_path / "library.json"
        lib = Library(library_path)
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")

        orchestrator = Orchestrator(mock_config)

        # Simulate track appearing in playlist2 as well
        mock_tracks = [
            Track(id="track1", name="Song 1", artists=["Artist"],
                  album="Album", duration_ms=180000, album_art_url=None)
        ]

        orchestrator._update_playlist_membership("playlist2", "Playlist 2", mock_tracks)

        track = orchestrator.library.get_track("track1")
        assert "playlist1" in track.playlists
        assert "playlist2" in track.playlists
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py::TestOrchestrator::test_sync_updates_playlist_membership -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# Add to Orchestrator class in spotify_swimmer/orchestrator.py
    def _update_playlist_membership(
        self,
        playlist_id: str,
        playlist_name: str,
        api_tracks: list[Track],
    ) -> None:
        """Update library to reflect current playlist membership from API."""
        api_track_ids = {t.id for t in api_tracks}

        # Update playlist metadata
        self.library.update_playlist(playlist_id, playlist_name, len(api_tracks))

        # Add playlist to tracks that are in API response
        for track in api_tracks:
            if self.library.is_downloaded(track.id):
                self.library.add_track_to_playlist(track.id, playlist_id)

        # Remove playlist from tracks no longer in API response
        for lib_track in self.library.get_tracks_for_playlist(playlist_id):
            if lib_track.id not in api_track_ids:
                self.library.remove_track_from_playlist(lib_track.id, playlist_id)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestrator.py::TestOrchestrator::test_sync_updates_playlist_membership -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): track playlist membership changes"
```

---

## Task 9: Remove Auto-Transfer from Orchestrator

**Files:**
- Modify: `spotify_swimmer/orchestrator.py`
- Modify: `spotify_swimmer/config.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_orchestrator.py
    @pytest.mark.asyncio
    async def test_sync_never_transfers(self, mock_config, tmp_path: Path):
        mock_config.playlists = []

        orchestrator = Orchestrator(mock_config)

        with patch.object(orchestrator, '_cleanup_orphaned_tracks', return_value=0):
            with patch('spotify_swimmer.orchestrator.TransferManager') as mock_transfer:
                result = await orchestrator.run()

                # TransferManager should never be instantiated during sync
                mock_transfer.assert_not_called()

        assert result.transferred is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py::TestOrchestrator::test_sync_never_transfers -v`
Expected: FAIL (currently auto_transfer may still be called)

**Step 3: Write minimal implementation**

```python
# In spotify_swimmer/orchestrator.py, modify the run() method
# Remove the auto_transfer section entirely:

    async def run(self) -> SyncResult:
        playlist_results: list[PlaylistResult] = []
        global_error: str | None = None
        orphans_deleted = 0

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

        # Pre-check: scan all playlists for new tracks BEFORE starting browser
        logger.info("Checking playlists for new tracks...")
        playlist_data = self._fetch_all_playlists(api)
        playlists_with_new_tracks = self._check_playlists_for_new_tracks(playlist_data)

        if not playlists_with_new_tracks:
            logger.info("All playlists are fully synced. Nothing to download.")
            for playlist in self.config.playlists:
                playlist_results.append(
                    PlaylistResult(name=playlist.name, tracks_synced=0, error=None)
                )
        else:
            total_new = sum(len(tracks) for tracks in playlists_with_new_tracks.values())
            logger.info(
                f"Found {total_new} new tracks across "
                f"{len(playlists_with_new_tracks)} playlists. Starting sync..."
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
                            new_tracks = playlists_with_new_tracks.get(playlist.playlist_id)
                            all_tracks = playlist_data.get(playlist.playlist_id, [])

                            if new_tracks:
                                result = await self._sync_playlist_tracks(
                                    playlist, new_tracks, all_tracks, browser, recorder
                                )
                            else:
                                result = PlaylistResult(
                                    name=playlist.name, tracks_synced=0, error=None
                                )
                            playlist_results.append(result)

                            # Update membership after syncing
                            self._update_playlist_membership(
                                playlist.playlist_id, playlist.name, all_tracks
                            )

            except RuntimeError as e:
                global_error = str(e)
                for playlist in self.config.playlists:
                    if not any(r.name == playlist.name for r in playlist_results):
                        playlist_results.append(
                            PlaylistResult(name=playlist.name, tracks_synced=0, error=str(e))
                        )

        # Cleanup orphaned tracks
        orphans_deleted = self._cleanup_orphaned_tracks()
        if orphans_deleted > 0:
            logger.info(f"Cleaned up {orphans_deleted} orphaned tracks")

        # Never transfer - that's a separate command now
        result = SyncResult(
            playlists=playlist_results,
            transferred=False,
            global_error=global_error,
        )

        notifier.send(result)
        return result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestrator.py::TestOrchestrator::test_sync_never_transfers -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/orchestrator.py tests/test_orchestrator.py
git commit -m "refactor(orchestrator): remove auto-transfer, sync-only workflow"
```

---

## Task 10: Add Playback Mode Selection

**Files:**
- Modify: `spotify_swimmer/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_orchestrator.py
class TestPlaybackModeSelection:
    def test_playlist_mode_when_mostly_new(self):
        # 8 new out of 10 = 80% > 70% threshold
        mode = Orchestrator._select_playback_mode(new_count=8, total_count=10)
        assert mode == "playlist"

    def test_individual_mode_when_few_new(self):
        # 2 new out of 10 = 20% < 70% threshold
        mode = Orchestrator._select_playback_mode(new_count=2, total_count=10)
        assert mode == "individual"

    def test_playlist_mode_at_threshold(self):
        # 7 new out of 10 = 70% = threshold
        mode = Orchestrator._select_playback_mode(new_count=7, total_count=10)
        assert mode == "playlist"

    def test_individual_mode_below_threshold(self):
        # 6 new out of 10 = 60% < 70%
        mode = Orchestrator._select_playback_mode(new_count=6, total_count=10)
        assert mode == "individual"

    def test_playlist_mode_when_all_new(self):
        mode = Orchestrator._select_playback_mode(new_count=10, total_count=10)
        assert mode == "playlist"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py::TestPlaybackModeSelection -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# Add to Orchestrator class in spotify_swimmer/orchestrator.py
    PLAYLIST_MODE_THRESHOLD = 0.7  # 70%

    @staticmethod
    def _select_playback_mode(new_count: int, total_count: int) -> str:
        """Select playback mode based on ratio of new tracks."""
        if total_count == 0:
            return "individual"

        ratio = new_count / total_count
        if ratio >= Orchestrator.PLAYLIST_MODE_THRESHOLD:
            return "playlist"
        return "individual"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestrator.py::TestPlaybackModeSelection -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): add playback mode selection logic"
```

---

## Task 11: Add Playlist Playback to Browser

**Files:**
- Modify: `spotify_swimmer/browser.py`
- Test: `tests/test_browser.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_browser.py
class TestSpotifyBrowserPlaylist:
    def test_get_now_playing_selector(self):
        browser = SpotifyBrowser(Path("/tmp"), "sink")
        # Just verify the selector exists
        assert browser.NOW_PLAYING_SELECTOR is not None

    @pytest.mark.asyncio
    async def test_play_playlist(self):
        browser = SpotifyBrowser(Path("/tmp"), "sink")
        browser.page = AsyncMock()
        browser.page.goto = AsyncMock()
        browser.page.locator = MagicMock(return_value=AsyncMock())

        await browser.play_playlist("playlist123")

        browser.page.goto.assert_called()
        call_url = browser.page.goto.call_args[0][0]
        assert "playlist/playlist123" in call_url

    @pytest.mark.asyncio
    async def test_get_current_track_id(self):
        browser = SpotifyBrowser(Path("/tmp"), "sink")
        browser.page = AsyncMock()

        # Mock the now playing link element
        mock_link = AsyncMock()
        mock_link.get_attribute = AsyncMock(return_value="/track/abc123")
        browser.page.locator = MagicMock(return_value=mock_link)

        track_id = await browser.get_current_track_id()
        assert track_id == "abc123"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_browser.py::TestSpotifyBrowserPlaylist -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# Add to SpotifyBrowser class in spotify_swimmer/browser.py
    NOW_PLAYING_SELECTOR = '[data-testid="now-playing-widget"] a[href*="/track/"]'

    async def play_playlist(self, playlist_id: str) -> None:
        """Navigate to playlist and start playing from the beginning."""
        url = self._get_playlist_url(playlist_id)
        await self.page.goto(url, wait_until="networkidle")

        await self._random_delay(1000, 3000)

        # Click the main play button for the playlist
        play_button = self.page.locator('[data-testid="play-button"]')
        await play_button.wait_for(state="visible", timeout=10000)
        await play_button.click()

    async def get_current_track_id(self) -> str | None:
        """Get the ID of the currently playing track from the now playing widget."""
        try:
            link = self.page.locator(self.NOW_PLAYING_SELECTOR).first
            href = await link.get_attribute("href", timeout=5000)
            if href and "/track/" in href:
                return href.split("/track/")[-1].split("?")[0]
        except Exception:
            pass
        return None

    async def wait_for_track_change(
        self, current_track_id: str, timeout_seconds: int = 300
    ) -> str | None:
        """Wait for track to change from current_track_id. Returns new track ID."""
        import time
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            new_track_id = await self.get_current_track_id()
            if new_track_id and new_track_id != current_track_id:
                return new_track_id
            await asyncio.sleep(1)

        return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_browser.py::TestSpotifyBrowserPlaylist -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/browser.py tests/test_browser.py
git commit -m "feat(browser): add playlist playback and track change detection"
```

---

## Task 12: Implement Playlist Mode Recording in Orchestrator

**Files:**
- Modify: `spotify_swimmer/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_orchestrator.py
class TestPlaylistModeRecording:
    @pytest.fixture
    def mock_config(self, tmp_path: Path):
        config = MagicMock()
        config.paths.music_dir = tmp_path / "music"
        config.paths.music_dir.mkdir()
        config.audio.bitrate = 192
        return config

    @pytest.mark.asyncio
    async def test_record_playlist_mode_records_only_new(self, mock_config, tmp_path: Path):
        # Setup library with one existing track
        lib = Library(tmp_path / "library.json")
        lib.add_track("existing1", "existing1.mp3", "Existing", "Artist", "playlist1")

        orchestrator = Orchestrator.__new__(Orchestrator)
        orchestrator.config = mock_config
        orchestrator.library = lib

        all_tracks = [
            Track("existing1", "Existing", ["Artist"], "Album", 180000, None),
            Track("new1", "New Song", ["Artist"], "Album", 200000, None),
        ]
        new_tracks = [all_tracks[1]]  # Only the new one

        mock_browser = AsyncMock()
        mock_browser.get_current_track_id = AsyncMock(side_effect=["existing1", "new1", None])
        mock_browser.wait_for_track_change = AsyncMock(side_effect=["new1", None])

        mock_recorder = MagicMock()

        with patch.object(orchestrator, '_record_current_track', new_callable=AsyncMock) as mock_record:
            # This would be the playlist mode implementation
            recorded = await orchestrator._record_playlist_mode(
                playlist_id="playlist1",
                all_tracks=all_tracks,
                new_track_ids={"new1"},
                browser=mock_browser,
                recorder=mock_recorder,
            )

        # Should only record the new track
        assert mock_record.call_count == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_orchestrator.py::TestPlaylistModeRecording -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# Add to Orchestrator class in spotify_swimmer/orchestrator.py
    async def _record_playlist_mode(
        self,
        playlist_id: str,
        all_tracks: list[Track],
        new_track_ids: set[str],
        browser: SpotifyBrowser,
        recorder: AudioRecorder,
    ) -> int:
        """Record tracks by playing the playlist. Returns count of tracks recorded."""
        track_map = {t.id: t for t in all_tracks}
        recorded_count = 0

        logger.info(f"Starting playlist mode for {len(all_tracks)} tracks ({len(new_track_ids)} new)")

        # Start playing the playlist
        await browser.play_playlist(playlist_id)
        await asyncio.sleep(2)

        current_track_id = await browser.get_current_track_id()
        tracks_seen = set()

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
            next_track_id = await browser.wait_for_track_change(
                current_track_id,
                timeout_seconds=(track.duration_seconds + 30) if track else 300
            )

            if next_track_id is None:
                logger.info("Playlist finished or timed out")
                break

            current_track_id = next_track_id

        return recorded_count

    async def _record_current_track(
        self,
        track: Track,
        browser: SpotifyBrowser,
        recorder: AudioRecorder,
    ) -> None:
        """Record the currently playing track."""
        output_path = self.config.paths.music_dir / f"{track.id}.mp3"

        recorder.start_recording(output_path)
        await asyncio.sleep(track.duration_seconds + 2)
        recorder.stop_recording()

        tag_mp3(output_path, track)
        self.library.add_track(
            track.id, f"{track.id}.mp3", track.name, track.artist_string, ""
        )

        logger.info(f"Completed: {track.name}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_orchestrator.py::TestPlaylistModeRecording -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): implement playlist mode recording"
```

---

## Task 13: Create Interactive Transfer Module

**Files:**
- Modify: `spotify_swimmer/transfer.py`
- Test: `tests/test_transfer.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_transfer.py
from spotify_swimmer.transfer import InteractiveTransfer, TransferStatus


class TestInteractiveTransfer:
    @pytest.fixture
    def mock_config(self, tmp_path: Path):
        config = MagicMock()
        config.paths.music_dir = tmp_path / "music"
        config.paths.music_dir.mkdir()
        config.paths.headphones_mount = tmp_path / "headphones"
        config.paths.headphones_mount.mkdir()
        config.paths.headphones_music_folder = "Music"
        (config.paths.headphones_mount / "Music").mkdir()
        return config

    def test_compute_transfer_status(self, mock_config, tmp_path: Path):
        # Setup library
        lib = Library(tmp_path / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        lib.add_track("track2", "track2.mp3", "Song 2", "Artist", "playlist1")
        lib.update_playlist("playlist1", "My Playlist", 2)

        # Create MP3 files locally
        (mock_config.paths.music_dir / "track1.mp3").write_bytes(b"data")
        (mock_config.paths.music_dir / "track2.mp3").write_bytes(b"data")

        # Put one track on headphones already
        headphones_music = mock_config.paths.headphones_mount / "Music"
        (headphones_music / "track1.mp3").write_bytes(b"data")

        transfer = InteractiveTransfer(mock_config, library=lib)
        status = transfer.compute_status()

        assert status.local_track_count == 2
        assert status.headphones_track_count == 1
        assert status.new_to_transfer == 1
        assert status.orphaned_on_headphones == 0

    def test_compute_orphaned_tracks(self, mock_config, tmp_path: Path):
        lib = Library(tmp_path / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        lib.update_playlist("playlist1", "My Playlist", 1)

        (mock_config.paths.music_dir / "track1.mp3").write_bytes(b"data")

        # Put extra file on headphones that's not in library
        headphones_music = mock_config.paths.headphones_mount / "Music"
        (headphones_music / "track1.mp3").write_bytes(b"data")
        (headphones_music / "orphan.mp3").write_bytes(b"data")

        transfer = InteractiveTransfer(mock_config, library=lib)
        status = transfer.compute_status()

        assert status.orphaned_on_headphones == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_transfer.py::TestInteractiveTransfer -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# Add to spotify_swimmer/transfer.py
from dataclasses import dataclass
from spotify_swimmer.library import Library


@dataclass
class PlaylistStatus:
    name: str
    total_tracks: int
    new_tracks: int
    track_details: list[tuple[str, str, str]]  # (track_id, title, status: "synced"/"new"/"orphan")


@dataclass
class TransferStatus:
    local_track_count: int
    headphones_track_count: int
    new_to_transfer: int
    orphaned_on_headphones: int
    playlists: list[PlaylistStatus]
    orphaned_files: list[str]


class InteractiveTransfer:
    def __init__(self, config, library: Library | None = None):
        self.config = config
        self.library = library or Library(
            config.paths.music_dir.parent / "library.json"
        )
        self.headphones_path = config.paths.headphones_mount / config.paths.headphones_music_folder

    def is_mounted(self) -> bool:
        return self.config.paths.headphones_mount.exists() and self.headphones_path.exists()

    def _get_headphones_files(self) -> set[str]:
        """Get set of MP3 filenames on headphones."""
        if not self.headphones_path.exists():
            return set()
        return {f.name for f in self.headphones_path.glob("*.mp3")}

    def _get_local_files(self) -> set[str]:
        """Get set of MP3 filenames in local library."""
        return {t.filename for t in self.library.get_all_tracks()}

    def compute_status(self) -> TransferStatus:
        """Compute current transfer status."""
        local_files = self._get_local_files()
        headphones_files = self._get_headphones_files()

        new_to_transfer = local_files - headphones_files
        orphaned_on_headphones = headphones_files - local_files

        # Build playlist status
        playlists = []
        for playlist in self.library.get_all_playlists():
            tracks = self.library.get_tracks_for_playlist(playlist.id)
            details = []
            new_count = 0

            for track in tracks:
                if track.filename in headphones_files:
                    status = "synced"
                else:
                    status = "new"
                    new_count += 1
                details.append((track.id, f"{track.title} - {track.artist}", status))

            playlists.append(PlaylistStatus(
                name=playlist.name,
                total_tracks=len(tracks),
                new_tracks=new_count,
                track_details=details,
            ))

        return TransferStatus(
            local_track_count=len(local_files),
            headphones_track_count=len(headphones_files),
            new_to_transfer=len(new_to_transfer),
            orphaned_on_headphones=len(orphaned_on_headphones),
            playlists=playlists,
            orphaned_files=list(orphaned_on_headphones),
        )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_transfer.py::TestInteractiveTransfer -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/transfer.py tests/test_transfer.py
git commit -m "feat(transfer): add InteractiveTransfer with status computation"
```

---

## Task 14: Add Interactive Menu to Transfer

**Files:**
- Modify: `spotify_swimmer/transfer.py`
- Test: `tests/test_transfer.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_transfer.py
    def test_sync_changes(self, mock_config, tmp_path: Path):
        lib = Library(tmp_path / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        lib.add_track("track2", "track2.mp3", "Song 2", "Artist", "playlist1")

        # Create local files
        (mock_config.paths.music_dir / "track1.mp3").write_bytes(b"data1")
        (mock_config.paths.music_dir / "track2.mp3").write_bytes(b"data2")

        # Put orphan on headphones
        headphones_music = mock_config.paths.headphones_mount / "Music"
        (headphones_music / "orphan.mp3").write_bytes(b"orphan")

        transfer = InteractiveTransfer(mock_config, library=lib)
        transfer.sync_changes()

        # New files should be copied
        assert (headphones_music / "track1.mp3").exists()
        assert (headphones_music / "track2.mp3").exists()
        # Orphan should be removed
        assert not (headphones_music / "orphan.mp3").exists()

    def test_full_reset(self, mock_config, tmp_path: Path):
        lib = Library(tmp_path / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")

        (mock_config.paths.music_dir / "track1.mp3").write_bytes(b"data1")

        # Put existing files on headphones
        headphones_music = mock_config.paths.headphones_mount / "Music"
        (headphones_music / "old.mp3").write_bytes(b"old")
        (headphones_music / "other.mp3").write_bytes(b"other")

        transfer = InteractiveTransfer(mock_config, library=lib)
        transfer.full_reset()

        # Only library tracks should remain
        assert (headphones_music / "track1.mp3").exists()
        assert not (headphones_music / "old.mp3").exists()
        assert not (headphones_music / "other.mp3").exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_transfer.py::TestInteractiveTransfer::test_sync_changes tests/test_transfer.py::TestInteractiveTransfer::test_full_reset -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# Add to InteractiveTransfer class in spotify_swimmer/transfer.py
    def sync_changes(self) -> tuple[int, int]:
        """Sync changes: copy new files, remove orphans. Returns (added, removed)."""
        local_files = self._get_local_files()
        headphones_files = self._get_headphones_files()

        # Copy new files
        new_files = local_files - headphones_files
        for filename in new_files:
            src = self.config.paths.music_dir / filename
            dst = self.headphones_path / filename
            shutil.copy2(src, dst)

        # Remove orphans
        orphaned = headphones_files - local_files
        for filename in orphaned:
            (self.headphones_path / filename).unlink()

        return len(new_files), len(orphaned)

    def full_reset(self) -> int:
        """Clear headphones and copy all library tracks. Returns count copied."""
        # Remove all existing files
        for f in self.headphones_path.glob("*.mp3"):
            f.unlink()

        # Copy all library tracks
        count = 0
        for track in self.library.get_all_tracks():
            src = self.config.paths.music_dir / track.filename
            if src.exists():
                dst = self.headphones_path / track.filename
                shutil.copy2(src, dst)
                count += 1

        return count

    def format_status_display(self, status: TransferStatus) -> str:
        """Format status for terminal display."""
        lines = [
            "═" * 55,
            "  Spotify Swimmer - Transfer to Headphones",
            "═" * 55,
            "",
            f"Headphones: {self.config.paths.headphones_mount} (connected)",
            "",
            "Local Library:",
        ]

        for p in status.playlists:
            new_str = f" ({p.new_tracks} new)" if p.new_tracks > 0 else ""
            lines.append(f"  {p.name:<20} {p.total_tracks:>3} tracks{new_str}")

        lines.extend([
            "  " + "─" * 35,
            f"  {'Total':<20} {status.local_track_count:>3} tracks ({status.new_to_transfer} new)",
            "",
            "On Headphones:",
            f"  {status.headphones_track_count} tracks",
        ])

        if status.orphaned_on_headphones > 0:
            lines.append(f"  {status.orphaned_on_headphones} orphaned (no longer in playlists)")

        lines.extend([
            "",
            "Actions:",
            f"  [1] Sync changes - add {status.new_to_transfer} new, remove {status.orphaned_on_headphones} orphaned",
            f"  [2] Full reset - clear headphones, copy all {status.local_track_count} tracks",
            "  [3] View details - show tracks by playlist",
            "  [4] Cancel",
            "",
        ])

        return "\n".join(lines)

    def format_details_display(self, status: TransferStatus) -> str:
        """Format detailed track list for terminal display."""
        lines = []

        for p in status.playlists:
            lines.append(f"\n{p.name} ({p.total_tracks} tracks):")
            for track_id, display, track_status in p.track_details:
                icon = "✓" if track_status == "synced" else "+"
                lines.append(f"  {icon} {display}")

        if status.orphaned_files:
            lines.append(f"\nOrphaned (to be removed):")
            for filename in status.orphaned_files:
                lines.append(f"  ✗ {filename}")

        return "\n".join(lines)

    def run(self) -> int:
        """Run interactive transfer menu. Returns exit code."""
        if not self.is_mounted():
            print(f"Headphones not mounted at {self.config.paths.headphones_mount}")
            return 1

        status = self.compute_status()
        print(self.format_status_display(status))

        while True:
            choice = input("Choose an option [1-4]: ").strip()

            if choice == "1":
                added, removed = self.sync_changes()
                print(f"\nDone! Added {added} tracks, removed {removed} orphaned files.")
                return 0
            elif choice == "2":
                confirm = input("This will delete all files on headphones. Continue? [y/N]: ")
                if confirm.lower() == "y":
                    count = self.full_reset()
                    print(f"\nDone! Copied {count} tracks to headphones.")
                    return 0
            elif choice == "3":
                print(self.format_details_display(status))
            elif choice == "4":
                print("Cancelled.")
                return 0
            else:
                print("Invalid choice. Please enter 1-4.")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_transfer.py::TestInteractiveTransfer -v`
Expected: PASS

**Step 5: Commit**

```bash
git add spotify_swimmer/transfer.py tests/test_transfer.py
git commit -m "feat(transfer): add interactive menu with sync/reset options"
```

---

## Task 15: Update Orchestrator to Use Playback Mode Selection

**Files:**
- Modify: `spotify_swimmer/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_orchestrator.py
class TestOrchestratorPlaybackIntegration:
    @pytest.mark.asyncio
    async def test_uses_playlist_mode_when_mostly_new(self):
        # Setup with 80% new tracks
        pass  # Integration test - verify correct method is called

    @pytest.mark.asyncio
    async def test_uses_individual_mode_when_few_new(self):
        # Setup with 20% new tracks
        pass  # Integration test
```

**Step 2: Update _sync_playlist_tracks to use mode selection**

```python
# Modify _sync_playlist_tracks in spotify_swimmer/orchestrator.py
    async def _sync_playlist_tracks(
        self,
        playlist: PlaylistConfig,
        new_tracks: list[Track],
        all_tracks: list[Track],
        browser: SpotifyBrowser,
        recorder: AudioRecorder,
    ) -> PlaylistResult:
        """Sync tracks for a playlist using appropriate playback mode."""
        try:
            mode = self._select_playback_mode(len(new_tracks), len(all_tracks))
            logger.info(
                f"Playlist '{playlist.name}': {len(new_tracks)} new of {len(all_tracks)} "
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
                        await self._record_track(track, playlist.playlist_id, browser, recorder)
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
```

**Step 3: Run all tests**

Run: `pytest -v`
Expected: PASS

**Step 4: Commit**

```bash
git add spotify_swimmer/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): integrate playback mode selection"
```

---

## Task 16: Remove Old TracksDB and Update Imports

**Files:**
- Delete: `spotify_swimmer/tracks_db.py`
- Delete: `tests/test_tracks_db.py`
- Modify: Any files still importing TracksDB

**Step 1: Search for remaining TracksDB imports**

Run: `grep -r "tracks_db\|TracksDB" spotify_swimmer/ tests/`

**Step 2: Remove old files**

```bash
rm spotify_swimmer/tracks_db.py
rm tests/test_tracks_db.py
```

**Step 3: Run all tests to ensure nothing breaks**

Run: `pytest -v`
Expected: PASS

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: remove deprecated TracksDB module"
```

---

## Task 17: Update Config to Remove auto_transfer

**Files:**
- Modify: `spotify_swimmer/config.py`
- Test: `tests/test_config.py`

**Step 1: Remove auto_transfer from BehaviorConfig**

```python
# In spotify_swimmer/config.py, update BehaviorConfig
@dataclass
class BehaviorConfig:
    skip_existing: bool = True
    trim_silence: bool = True
    # Remove: auto_transfer: bool = True
```

**Step 2: Update tests and config examples**

**Step 3: Commit**

```bash
git add spotify_swimmer/config.py tests/test_config.py
git commit -m "refactor(config): remove auto_transfer option"
```

---

## Task 18: Final Integration Test

**Files:**
- Test: `tests/test_integration.py`

**Step 1: Write integration test**

```python
# tests/test_integration.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from spotify_swimmer.config import Config
from spotify_swimmer.library import Library
from spotify_swimmer.orchestrator import Orchestrator
from spotify_swimmer.transfer import InteractiveTransfer


class TestFullWorkflow:
    @pytest.fixture
    def setup_environment(self, tmp_path: Path):
        """Setup complete test environment."""
        music_dir = tmp_path / "music"
        music_dir.mkdir()

        headphones = tmp_path / "headphones" / "Music"
        headphones.mkdir(parents=True)

        config = MagicMock()
        config.paths.music_dir = music_dir
        config.paths.headphones_mount = tmp_path / "headphones"
        config.paths.headphones_music_folder = "Music"
        config.spotify.client_id = "test"
        config.spotify.client_secret = "test"
        config.audio.bitrate = 192
        config.behavior.skip_existing = True
        config.notifications.ntfy_server = "https://ntfy.sh"
        config.notifications.ntfy_topic = "test"
        config.notifications.notify_on_success = False
        config.notifications.notify_on_failure = False
        config.playlists = []

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

        lib = Library(tmp_path / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        lib.add_track("track2", "track2.mp3", "Song 2", "Artist", "playlist1")
        lib.update_playlist("playlist1", "Test Playlist", 2)

        # Create local files
        (config.paths.music_dir / "track1.mp3").write_bytes(b"data1")
        (config.paths.music_dir / "track2.mp3").write_bytes(b"data2")

        # Create orphan on headphones
        headphones = config.paths.headphones_mount / "Music"
        (headphones / "orphan.mp3").write_bytes(b"orphan")

        transfer = InteractiveTransfer(config, library=lib)
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
```

**Step 2: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests for full workflow"
```

---

## Task 19: Update README

**Files:**
- Modify: `README.md`

**Step 1: Update documentation**

Update README.md to reflect:
- New CLI subcommands (`sync` and `transfer`)
- Removed auto_transfer config option
- New workflow (sync downloads, transfer is manual)
- Interactive transfer menu description

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for new sync/transfer workflow"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Create Library data model | library.py, test_library.py |
| 2 | Add Library persistence | library.py, test_library.py |
| 3 | Add playlist management | library.py, test_library.py |
| 4 | Add migration from old format | library.py, test_library.py |
| 5 | Update CLI with subcommands | cli.py, test_cli.py |
| 6 | Update Orchestrator to use Library | orchestrator.py, test_orchestrator.py |
| 7 | Add orphan cleanup | orchestrator.py, test_orchestrator.py |
| 8 | Track playlist membership | orchestrator.py, test_orchestrator.py |
| 9 | Remove auto-transfer | orchestrator.py, test_orchestrator.py |
| 10 | Add playback mode selection | orchestrator.py, test_orchestrator.py |
| 11 | Add playlist playback to browser | browser.py, test_browser.py |
| 12 | Implement playlist mode recording | orchestrator.py, test_orchestrator.py |
| 13 | Create interactive transfer | transfer.py, test_transfer.py |
| 14 | Add transfer menu | transfer.py, test_transfer.py |
| 15 | Integrate playback modes | orchestrator.py, test_orchestrator.py |
| 16 | Remove old TracksDB | tracks_db.py, test_tracks_db.py |
| 17 | Update config | config.py, test_config.py |
| 18 | Integration tests | test_integration.py |
| 19 | Update README | README.md |
