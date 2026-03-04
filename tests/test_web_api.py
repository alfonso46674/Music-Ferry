# tests/test_web_api.py
"""Tests for the Music Ferry web API."""

import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from music_ferry.config import (
    AudioConfig,
    BehaviorConfig,
    Config,
    NotificationsConfig,
    PathsConfig,
    SpotifyConfig,
    TransferConfig,
    YouTubeConfig,
)


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create a mock configuration for testing."""
    return Config(
        spotify=SpotifyConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            username="test_user",
            enabled=True,
            playlists=[],
        ),
        youtube=YouTubeConfig(
            enabled=False,
            playlists=[],
        ),
        audio=AudioConfig(bitrate=192, format="mp3"),
        paths=PathsConfig(
            music_dir=tmp_path / ".music-ferry",
            headphones_mount=tmp_path / "headphones",
        ),
        notifications=NotificationsConfig(
            ntfy_topic="test-topic",
        ),
        behavior=BehaviorConfig(),
        transfer=TransferConfig(),
    )


@pytest.fixture
def client(mock_config: Config) -> TestClient:
    """Create a test client with mock config."""
    from music_ferry.web import create_app

    app = create_app(mock_config)
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_healthy(self, client: TestClient):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestStatusEndpoint:
    def test_status_returns_sync_state(self, client: TestClient):
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert "syncing" in data
        assert "last_sync" in data
        assert data["syncing"] is False


class TestLibraryEndpoint:
    def test_library_returns_summary(self, client: TestClient, mock_config: Config):
        # Create the directories
        (mock_config.paths.music_dir / "spotify").mkdir(parents=True, exist_ok=True)
        (mock_config.paths.music_dir / "youtube").mkdir(parents=True, exist_ok=True)

        response = client.get("/api/v1/library")
        assert response.status_code == 200
        data = response.json()
        assert "spotify" in data
        assert "youtube" in data
        assert "total" in data
        assert data["total"]["tracks"] == 0

    def test_library_detail_spotify(self, client: TestClient, mock_config: Config):
        (mock_config.paths.music_dir / "spotify").mkdir(parents=True, exist_ok=True)

        response = client.get("/api/v1/library/spotify")
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "spotify"
        assert "tracks" in data
        assert "playlists" in data

    def test_library_detail_unknown_source(self, client: TestClient):
        response = client.get("/api/v1/library/unknown")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data


class TestConfigEndpoint:
    def test_config_redacts_secrets(self, client: TestClient):
        response = client.get("/api/v1/config")
        assert response.status_code == 200
        data = response.json()

        # Check that secrets are redacted
        assert data["spotify"]["client_id"] == "test****"
        assert data["spotify"]["client_secret"] == "test****"
        assert data["notifications"]["ntfy_topic"] == "test****"

        # Check that non-secrets are visible
        assert data["spotify"]["username"] == "test_user"
        assert data["audio"]["bitrate"] == 192


class TestSyncEndpoint:
    def test_sync_trigger_returns_job_id(self, client: TestClient):
        response = client.post("/api/v1/sync")
        assert response.status_code == 200
        data = response.json()
        # May return job_id or error if already syncing
        assert "job_id" in data or "error" in data

    def test_sync_status_not_found(self, client: TestClient):
        response = client.get("/api/v1/sync/nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert data["error"] == "Job not found"


class TestCLIServeCommand:
    def test_parse_serve_command(self):
        from music_ferry.cli import parse_args

        args = parse_args(["serve"])
        assert args.command == "serve"
        assert args.host == "127.0.0.1"
        assert args.port == 4444
        assert args.reload is False

    def test_parse_serve_with_options(self):
        from music_ferry.cli import parse_args

        args = parse_args(["serve", "--host", "0.0.0.0", "--port", "8080", "--reload"])
        assert args.command == "serve"
        assert args.host == "0.0.0.0"
        assert args.port == 8080
        assert args.reload is True
