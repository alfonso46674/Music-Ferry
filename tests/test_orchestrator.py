# tests/test_orchestrator.py
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from spotify_swimmer.orchestrator import Orchestrator
from spotify_swimmer.config import (
    Config, SpotifyConfig, PlaylistConfig, AudioConfig,
    PathsConfig, NotificationsConfig, BehaviorConfig
)
from spotify_swimmer.spotify_api import Track


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
        orchestrator.tracks_db.add_track("existing123", "existing123.mp3")

        tracks = [
            Track(id="existing123", name="Old Song", artists=["A"], album="B", duration_ms=180000, album_art_url=None),
            Track(id="new456", name="New Song", artists=["C"], album="D", duration_ms=200000, album_art_url=None),
        ]

        new_tracks = orchestrator._filter_new_tracks(tracks)

        assert len(new_tracks) == 1
        assert new_tracks[0].id == "new456"

    @pytest.mark.asyncio
    @patch("spotify_swimmer.orchestrator.tag_mp3")
    @patch("spotify_swimmer.orchestrator.asyncio.sleep", new_callable=AsyncMock)
    @patch("spotify_swimmer.orchestrator.SpotifyAPI")
    @patch("spotify_swimmer.orchestrator.SpotifyBrowser")
    @patch("spotify_swimmer.orchestrator.AudioRecorder")
    @patch("spotify_swimmer.orchestrator.Notifier")
    async def test_run_sync(
        self,
        mock_notifier_class,
        mock_recorder_class,
        mock_browser_class,
        mock_api_class,
        mock_sleep,
        mock_tag_mp3,
        sample_config: Config,
    ):
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

        orchestrator = Orchestrator(sample_config)
        result = await orchestrator.run()

        assert result.total_tracks == 1
        mock_api.get_playlist_tracks.assert_called_once()
        mock_notifier.send.assert_called_once()
