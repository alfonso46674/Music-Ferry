# tests/test_youtube_downloader.py
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest
from yt_dlp.utils import DownloadError

from music_ferry.spotify_api import Track
from music_ferry.youtube.downloader import YouTubeDownloader


class TestYouTubeDownloader:
    @pytest.fixture
    def downloader(self, tmp_path: Path):
        return YouTubeDownloader(output_dir=tmp_path / "music", bitrate=192)

    def test_init_creates_output_dir(self, tmp_path: Path):
        output_dir = tmp_path / "youtube" / "music"
        YouTubeDownloader(output_dir=output_dir, bitrate=192)
        assert output_dir.exists()

    @patch("music_ferry.youtube.downloader.yt_dlp.YoutubeDL")
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

    @patch("music_ferry.youtube.downloader.yt_dlp.YoutubeDL")
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
        ydl_opts = mock_ydl_class.call_args[0][0]
        assert ydl_opts["outtmpl"] == str(
            downloader.output_dir / "Rick Astley - Never Gonna Give You Up.%(ext)s"
        )
        assert result == downloader.output_dir / "Rick Astley - Never Gonna Give You Up.mp3"

    @patch("music_ferry.youtube.downloader.yt_dlp.YoutubeDL")
    def test_download_track_passes_cookiefile(self, mock_ydl_class, tmp_path: Path):
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)

        cookies_path = tmp_path / "youtube-cookies.txt"
        downloader = YouTubeDownloader(
            output_dir=tmp_path / "music",
            bitrate=192,
            cookies_file=cookies_path,
        )
        track = Track(
            id="dQw4w9WgXcQ",
            name="Never Gonna Give You Up",
            artists=["Rick Astley"],
            album="Test Playlist",
            duration_ms=213000,
            album_art_url=None,
            source="youtube",
        )

        downloader.download_track(track)

        ydl_opts = mock_ydl_class.call_args[0][0]
        assert ydl_opts["cookiefile"] == str(cookies_path)

    @patch("music_ferry.youtube.downloader.yt_dlp.YoutubeDL")
    def test_get_playlist_tracks_passes_cookiefile(
        self, mock_ydl_class, tmp_path: Path
    ):
        mock_ydl = MagicMock()
        mock_ydl_class.return_value.__enter__ = MagicMock(return_value=mock_ydl)
        mock_ydl_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"entries": []}

        cookies_path = tmp_path / "youtube-cookies.txt"
        downloader = YouTubeDownloader(
            output_dir=tmp_path / "music",
            bitrate=192,
            cookies_file=cookies_path,
        )

        downloader.get_playlist_tracks(
            "https://www.youtube.com/playlist?list=PLtest",
            playlist_name="Test Playlist",
        )

        ydl_opts = mock_ydl_class.call_args[0][0]
        assert ydl_opts["cookiefile"] == str(cookies_path)

    @patch("music_ferry.youtube.downloader.time.sleep")
    @patch("music_ferry.youtube.downloader.random.uniform")
    def test_download_tracks_with_delay(self, mock_random, mock_sleep, downloader):
        mock_random.return_value = 10.0

        tracks = [
            Track(
                id="vid1",
                name="Video 1",
                artists=["Ch1"],
                album="PL",
                duration_ms=100000,
                album_art_url=None,
                source="youtube",
            ),
            Track(
                id="vid2",
                name="Video 2",
                artists=["Ch2"],
                album="PL",
                duration_ms=100000,
                album_art_url=None,
                source="youtube",
            ),
        ]

        with patch.object(downloader, "download_track", return_value=Path("/fake.mp3")):
            downloaded, failed = downloader.download_tracks(tracks)

        assert len(downloaded) == 2
        assert failed == []
        # Should have slept between downloads (1 time for 2 tracks)
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(10.0)

    def test_download_tracks_handles_errors(self, downloader):
        """Test that download_tracks continues after individual failures."""
        tracks = [
            Track(
                id="vid1",
                name="Video 1",
                artists=["Ch1"],
                album="PL",
                duration_ms=100000,
                album_art_url=None,
                source="youtube",
            ),
            Track(
                id="vid2",
                name="Video 2",
                artists=["Ch2"],
                album="PL",
                duration_ms=100000,
                album_art_url=None,
                source="youtube",
            ),
        ]

        call_count = [0]

        def mock_download(track):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Network error")
            return Path("/fake.mp3")

        with patch.object(downloader, "download_track", side_effect=mock_download):
            with patch("music_ferry.youtube.downloader.time.sleep"):
                downloaded, failed = downloader.download_tracks(tracks)

        assert len(downloaded) == 1  # Only second track succeeded
        assert len(failed) == 1

    def test_is_retryable_error_http_status(self, downloader):
        http_error = HTTPError(
            url="https://www.youtube.com/watch?v=abc",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=None,
        )
        error = DownloadError("HTTP Error 403: Forbidden")
        error.__cause__ = http_error

        assert downloader._is_retryable_error(error) is True
