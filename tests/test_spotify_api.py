# tests/test_spotify_api.py
from unittest.mock import MagicMock, patch

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
