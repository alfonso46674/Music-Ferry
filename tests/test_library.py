# tests/test_library.py
import json
from pathlib import Path

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
