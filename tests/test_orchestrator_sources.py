# tests/test_orchestrator_sources.py
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from music_ferry.orchestrator import Orchestrator


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

        assert (
            orchestrator.spotify_library.db_path
            == tmp_path / "spotify" / "library.json"
        )
        assert (
            orchestrator.youtube_library.db_path
            == tmp_path / "youtube" / "library.json"
        )

    def test_orchestrator_creates_source_directories(self, mock_config, tmp_path):
        Orchestrator(mock_config)

        assert (tmp_path / "spotify" / "music").exists()
        assert (tmp_path / "youtube" / "music").exists()

    @pytest.mark.asyncio
    async def test_run_with_spotify_only(self, mock_config):
        with patch.object(
            Orchestrator, "_sync_spotify", new_callable=AsyncMock
        ) as mock_spotify:
            with patch.object(
                Orchestrator, "_sync_youtube", new_callable=AsyncMock
            ) as mock_youtube:
                mock_spotify.return_value = []
                mock_youtube.return_value = []

                orchestrator = Orchestrator(mock_config)
                await orchestrator.run(sync_spotify=True, sync_youtube=False)

                mock_spotify.assert_called_once()
                mock_youtube.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_with_youtube_only(self, mock_config):
        with patch.object(
            Orchestrator, "_sync_spotify", new_callable=AsyncMock
        ) as mock_spotify:
            with patch.object(
                Orchestrator, "_sync_youtube", new_callable=AsyncMock
            ) as mock_youtube:
                mock_spotify.return_value = []
                mock_youtube.return_value = []

                orchestrator = Orchestrator(mock_config)
                await orchestrator.run(sync_spotify=False, sync_youtube=True)

                mock_spotify.assert_not_called()
                mock_youtube.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_with_both_sources(self, mock_config):
        with patch.object(
            Orchestrator, "_sync_spotify", new_callable=AsyncMock
        ) as mock_spotify:
            with patch.object(
                Orchestrator, "_sync_youtube", new_callable=AsyncMock
            ) as mock_youtube:
                mock_spotify.return_value = []
                mock_youtube.return_value = []

                orchestrator = Orchestrator(mock_config)
                await orchestrator.run(sync_spotify=True, sync_youtube=True)

                mock_spotify.assert_called_once()
                mock_youtube.assert_called_once()
