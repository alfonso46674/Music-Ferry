# tests/test_config.py
import tempfile
from pathlib import Path

import pytest
import yaml

from music_ferry.config import Config, load_config


class TestConfig:
    def test_load_valid_config(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "spotify": {
                        "client_id": "test_id",
                        "client_secret": "test_secret",
                        "username": "test_user",
                    },
                    "playlists": [
                        {
                            "name": "Test Playlist",
                            "url": "https://open.spotify.com/playlist/abc123",
                        }
                    ],
                    "audio": {"bitrate": 192, "format": "mp3"},
                    "paths": {
                        "music_dir": "~/.music-ferry/music",
                        "headphones_mount": "/media/user/HEADPHONES",
                        "headphones_music_folder": "Music",
                    },
                    "notifications": {
                        "ntfy_topic": "test-topic",
                        "ntfy_server": "https://ntfy.sh",
                        "notify_on_success": False,
                        "notify_on_failure": True,
                    },
                    "behavior": {
                        "skip_existing": True,
                        "trim_silence": True,
                    },
                }
            )
        )

        config = load_config(config_file)

        assert config.spotify.client_id == "test_id"
        assert config.spotify.client_secret == "test_secret"
        assert config.spotify.username == "test_user"
        assert len(config.spotify.playlists) == 1
        assert config.spotify.playlists[0].name == "Test Playlist"
        assert config.audio.bitrate == 192
        assert config.paths.music_dir == Path.home() / ".music-ferry" / "music"
        assert config.notifications.ntfy_topic == "test-topic"
        assert config.behavior.skip_existing is True
        assert config.transfer.reserve_free_gb == 0.0

    def test_load_config_missing_required_field(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "spotify": {"client_id": "test_id"},  # missing client_secret
                }
            )
        )

        with pytest.raises(ValueError, match="client_secret"):
            load_config(config_file)

    def test_load_config_file_not_found(self, tmp_path: Path):
        config_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(FileNotFoundError):
            load_config(config_file)

    def test_playlist_id_extraction(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "spotify": {
                        "client_id": "test_id",
                        "client_secret": "test_secret",
                        "username": "test_user",
                    },
                    "playlists": [
                        {
                            "name": "Test",
                            "url": "https://open.spotify.com/playlist/37i9dQZEVXcQ9COmYvdajy",
                        }
                    ],
                    "audio": {"bitrate": 192, "format": "mp3"},
                    "paths": {
                        "music_dir": "~/.music-ferry/music",
                        "headphones_mount": "/media/user/HEADPHONES",
                        "headphones_music_folder": "Music",
                    },
                    "notifications": {
                        "ntfy_topic": "test-topic",
                        "ntfy_server": "https://ntfy.sh",
                        "notify_on_success": False,
                        "notify_on_failure": True,
                    },
                    "behavior": {
                        "skip_existing": True,
                        "trim_silence": True,
                    },
                }
            )
        )

        config = load_config(config_file)
        assert config.spotify.playlists[0].playlist_id == "37i9dQZEVXcQ9COmYvdajy"


class TestYouTubeConfig:
    def test_load_config_with_youtube_section(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "spotify": {
                        "enabled": True,
                        "client_id": "test_id",
                        "client_secret": "test_secret",
                        "username": "test_user",
                        "playlists": [
                            {
                                "name": "Test Playlist",
                                "url": "https://open.spotify.com/playlist/abc123",
                            }
                        ],
                    },
                    "youtube": {
                        "enabled": True,
                        "retry_count": 2,
                        "retry_delay_seconds": 7.5,
                        "cookies_file": "~/.music-ferry/cookies/youtube.txt",
                        "playlists": [
                            {
                                "name": "YT Playlist",
                                "url": "https://www.youtube.com/playlist?list=PLxxx",
                            }
                        ],
                    },
                    "audio": {"bitrate": 192, "format": "mp3"},
                    "paths": {
                        "music_dir": "~/.music-ferry",
                        "headphones_mount": "/media/user/HEADPHONES",
                        "headphones_music_folder": "Music",
                    },
                    "notifications": {
                        "ntfy_topic": "test-topic",
                        "ntfy_server": "https://ntfy.sh",
                        "notify_on_success": False,
                        "notify_on_failure": True,
                    },
                    "behavior": {
                        "skip_existing": True,
                        "trim_silence": True,
                    },
                }
            )
        )

        config = load_config(config_file)

        assert config.spotify.enabled is True
        assert len(config.spotify.playlists) == 1
        assert config.spotify.playlists[0].name == "Test Playlist"
        assert config.youtube.enabled is True
        assert len(config.youtube.playlists) == 1
        assert config.youtube.playlists[0].name == "YT Playlist"
        assert config.youtube.retry_count == 2
        assert config.youtube.retry_delay_seconds == 7.5
        assert (
            config.youtube.cookies_file
            == Path.home() / ".music-ferry" / "cookies" / "youtube.txt"
        )

    def test_load_config_youtube_disabled_by_default(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "spotify": {
                        "client_id": "test_id",
                        "client_secret": "test_secret",
                        "username": "test_user",
                        "playlists": [
                            {
                                "name": "Test",
                                "url": "https://open.spotify.com/playlist/abc123",
                            }
                        ],
                    },
                    "audio": {"bitrate": 192, "format": "mp3"},
                    "paths": {
                        "music_dir": "~/.music-ferry",
                        "headphones_mount": "/media/user/HEADPHONES",
                        "headphones_music_folder": "Music",
                    },
                    "notifications": {
                        "ntfy_topic": "test-topic",
                        "ntfy_server": "https://ntfy.sh",
                    },
                    "behavior": {"skip_existing": True, "trim_silence": True},
                }
            )
        )

        config = load_config(config_file)

        assert config.spotify.enabled is True
        assert config.youtube.enabled is False
        assert len(config.youtube.playlists) == 0
        assert config.youtube.cookies_file is None

    def test_load_config_migrates_root_playlists(self, tmp_path: Path):
        """Test backward compatibility: playlists at root level migrate to spotify.playlists."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "spotify": {
                        "client_id": "test_id",
                        "client_secret": "test_secret",
                        "username": "test_user",
                    },
                    "playlists": [
                        {
                            "name": "Old Format",
                            "url": "https://open.spotify.com/playlist/abc123",
                        }
                    ],
                    "audio": {"bitrate": 192, "format": "mp3"},
                    "paths": {
                        "music_dir": "~/.music-ferry",
                        "headphones_mount": "/media/user/HEADPHONES",
                        "headphones_music_folder": "Music",
                    },
                    "notifications": {
                        "ntfy_topic": "test-topic",
                        "ntfy_server": "https://ntfy.sh",
                    },
                    "behavior": {"skip_existing": True, "trim_silence": True},
                }
            )
        )

        config = load_config(config_file)

        assert len(config.spotify.playlists) == 1
        assert config.spotify.playlists[0].name == "Old Format"

    def test_load_config_spotify_disabled_no_credentials(self, tmp_path: Path):
        """Test that Spotify credentials are not required when disabled."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "spotify": {
                        "enabled": False,
                        # No client_id, client_secret, username
                    },
                    "youtube": {
                        "enabled": True,
                        "playlists": [
                            {
                                "name": "Test",
                                "url": "https://www.youtube.com/playlist?list=PLtest",
                            }
                        ],
                    },
                    "audio": {"bitrate": 192, "format": "mp3"},
                    "paths": {
                        "music_dir": "~/.music-ferry",
                        "headphones_mount": "/media/user/HEADPHONES",
                        "headphones_music_folder": "Music",
                    },
                    "notifications": {
                        "ntfy_topic": "test-topic",
                        "ntfy_server": "https://ntfy.sh",
                    },
                    "behavior": {"skip_existing": True, "trim_silence": True},
                }
            )
        )

        config = load_config(config_file)

        assert config.spotify.enabled is False
        assert config.spotify.client_id == ""
        assert config.youtube.enabled is True
        assert len(config.youtube.playlists) == 1


class TestYouTubePlaylistConfig:
    def test_youtube_playlist_id_extraction(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "spotify": {
                        "client_id": "test_id",
                        "client_secret": "test_secret",
                        "username": "test_user",
                        "playlists": [],
                    },
                    "youtube": {
                        "enabled": True,
                        "playlists": [
                            {
                                "name": "Test",
                                "url": "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
                            }
                        ],
                    },
                    "audio": {"bitrate": 192, "format": "mp3"},
                    "paths": {
                        "music_dir": "~/.music-ferry",
                        "headphones_mount": "/media/user/HEADPHONES",
                        "headphones_music_folder": "Music",
                    },
                    "notifications": {
                        "ntfy_topic": "test",
                        "ntfy_server": "https://ntfy.sh",
                    },
                    "behavior": {"skip_existing": True, "trim_silence": True},
                }
            )
        )

        config = load_config(config_file)

        assert (
            config.youtube.playlists[0].playlist_id
            == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        )
