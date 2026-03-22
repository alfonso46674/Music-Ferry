# tests/test_library.py
import json
from pathlib import Path

from music_ferry.library import Library, LibraryPlaylist, LibraryTrack


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


class TestLibraryPlaylist:
    def test_library_playlist_creation(self):
        playlist = LibraryPlaylist(
            id="playlist123",
            name="My Playlist",
            last_synced="2026-01-21T06:00:00",
            track_count=10,
        )
        assert playlist.id == "playlist123"
        assert playlist.name == "My Playlist"
        assert playlist.last_synced == "2026-01-21T06:00:00"
        assert playlist.track_count == 10


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

    def test_delete_track(self, tmp_path: Path):
        lib = Library(tmp_path / "library.json")
        lib.add_track("abc123", "abc123.mp3", "Song", "Artist", "playlist1")
        assert lib.is_downloaded("abc123") is True

        lib.delete_track("abc123")
        assert lib.is_downloaded("abc123") is False

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

    def test_migrate_from_old_format(self, tmp_path: Path):
        # Create old tracks.json format
        old_db = tmp_path / "tracks.json"
        old_db.write_text(
            json.dumps(
                {
                    "track1": "track1.mp3",
                    "track2": "track2.mp3",
                }
            )
        )

        lib = Library(tmp_path / "library.json", migrate_from=old_db)

        # Old tracks should be imported with empty playlists (orphaned)
        assert lib.is_downloaded("track1")
        assert lib.is_downloaded("track2")
        track = lib.get_track("track1")
        assert track.filename == "track1.mp3"
        # Title/artist unknown from old format
        assert track.title == "Unknown"
        assert track.playlists == []  # Will be populated on next sync

    def test_no_migration_if_library_exists(self, tmp_path: Path):
        # Create old tracks.json
        old_db = tmp_path / "tracks.json"
        old_db.write_text(json.dumps({"old_track": "old.mp3"}))

        # Create existing library.json
        lib_path = tmp_path / "library.json"
        lib1 = Library(lib_path)
        lib1.add_track("new_track", "new.mp3", "New Song", "Artist", "playlist1")

        # Open with migrate_from - should NOT migrate since library exists
        lib2 = Library(lib_path, migrate_from=old_db)

        assert lib2.is_downloaded("new_track")
        assert not lib2.is_downloaded("old_track")
