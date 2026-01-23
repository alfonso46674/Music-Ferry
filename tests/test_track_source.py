# tests/test_track_source.py
import pytest
from music_ferry.spotify_api import Track


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
