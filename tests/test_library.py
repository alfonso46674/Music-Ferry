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
