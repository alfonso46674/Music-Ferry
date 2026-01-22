# tests/test_integration.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from spotify_swimmer.library import Library
from spotify_swimmer.transfer import InteractiveTransfer


class TestFullWorkflow:
    @pytest.fixture
    def setup_environment(self, tmp_path: Path):
        """Setup complete test environment."""
        music_dir = tmp_path / "music"
        music_dir.mkdir()

        headphones = tmp_path / "headphones" / "Music"
        headphones.mkdir(parents=True)

        config = MagicMock()
        config.paths.music_dir = music_dir
        config.paths.headphones_mount = tmp_path / "headphones"
        config.paths.headphones_music_folder = "Music"
        config.spotify.client_id = "test"
        config.spotify.client_secret = "test"
        config.audio.bitrate = 192
        config.behavior.skip_existing = True
        config.notifications.ntfy_server = "https://ntfy.sh"
        config.notifications.ntfy_topic = "test"
        config.notifications.notify_on_success = False
        config.notifications.notify_on_failure = False
        config.spotify.playlists = []
        config.spotify.enabled = True
        config.youtube.enabled = False
        config.youtube.playlists = []

        return config, tmp_path

    def test_library_tracks_playlist_membership(self, setup_environment):
        config, tmp_path = setup_environment

        lib = Library(tmp_path / "library.json")

        # Add track to playlist1
        lib.add_track("track1", "track1.mp3", "Song", "Artist", "playlist1")
        assert lib.get_track("track1").playlists == ["playlist1"]

        # Add same track to playlist2
        lib.add_track_to_playlist("track1", "playlist2")
        assert set(lib.get_track("track1").playlists) == {"playlist1", "playlist2"}

        # Remove from playlist1
        lib.remove_track_from_playlist("track1", "playlist1")
        assert lib.get_track("track1").playlists == ["playlist2"]
        assert not lib.get_track("track1").is_orphaned

        # Remove from playlist2 - now orphaned
        lib.remove_track_from_playlist("track1", "playlist2")
        assert lib.get_track("track1").is_orphaned

    def test_transfer_syncs_correctly(self, setup_environment):
        config, tmp_path = setup_environment

        # Setup spotify source directory structure
        spotify_dir = config.paths.music_dir / "spotify"
        spotify_music = spotify_dir / "music"
        spotify_music.mkdir(parents=True)

        lib = Library(spotify_dir / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        lib.add_track("track2", "track2.mp3", "Song 2", "Artist", "playlist1")
        lib.update_playlist("playlist1", "Test Playlist", 2)

        # Create local files in spotify music dir
        (spotify_music / "track1.mp3").write_bytes(b"data1")
        (spotify_music / "track2.mp3").write_bytes(b"data2")

        # Create orphan on headphones
        headphones = config.paths.headphones_mount / "Music"
        (headphones / "orphan.mp3").write_bytes(b"orphan")

        transfer = InteractiveTransfer(config, sources=["spotify"], spotify_library=lib)
        status = transfer.compute_status()

        assert status.local_track_count == 2
        assert status.new_to_transfer == 2
        assert status.orphaned_on_headphones == 1

        added, removed = transfer.sync_changes()

        assert added == 2
        assert removed == 1
        assert (headphones / "track1.mp3").exists()
        assert (headphones / "track2.mp3").exists()
        assert not (headphones / "orphan.mp3").exists()

    def test_full_reset_clears_headphones(self, setup_environment):
        config, tmp_path = setup_environment

        # Setup spotify source directory structure
        spotify_dir = config.paths.music_dir / "spotify"
        spotify_music = spotify_dir / "music"
        spotify_music.mkdir(parents=True)

        lib = Library(spotify_dir / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")

        # Create local file in spotify music dir
        (spotify_music / "track1.mp3").write_bytes(b"data1")

        # Put old files on headphones
        headphones = config.paths.headphones_mount / "Music"
        (headphones / "old1.mp3").write_bytes(b"old1")
        (headphones / "old2.mp3").write_bytes(b"old2")

        transfer = InteractiveTransfer(config, sources=["spotify"], spotify_library=lib)
        copied = transfer.full_reset()

        assert copied == 1
        assert (headphones / "track1.mp3").exists()
        assert not (headphones / "old1.mp3").exists()
        assert not (headphones / "old2.mp3").exists()

    def test_playback_mode_selection(self):
        from spotify_swimmer.orchestrator import Orchestrator

        # 100% new -> playlist mode
        assert Orchestrator._select_playback_mode(10, 10) == "playlist"

        # 70% new -> playlist mode (at threshold)
        assert Orchestrator._select_playback_mode(7, 10) == "playlist"

        # 60% new -> individual mode
        assert Orchestrator._select_playback_mode(6, 10) == "individual"

        # 0% new -> individual mode
        assert Orchestrator._select_playback_mode(0, 10) == "individual"

        # Empty playlist -> individual mode
        assert Orchestrator._select_playback_mode(0, 0) == "individual"

    def test_library_persistence(self, setup_environment):
        config, tmp_path = setup_environment
        lib_path = tmp_path / "library.json"

        # Create library with data
        lib1 = Library(lib_path)
        lib1.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        lib1.add_track("track2", "track2.mp3", "Song 2", "Artist", "playlist1")
        lib1.update_playlist("playlist1", "My Playlist", 2)

        # Load in new instance
        lib2 = Library(lib_path)
        assert lib2.is_downloaded("track1")
        assert lib2.is_downloaded("track2")
        assert lib2.get_track("track1").title == "Song 1"

        playlist = lib2.get_playlist("playlist1")
        assert playlist is not None
        assert playlist.name == "My Playlist"
        assert playlist.track_count == 2
