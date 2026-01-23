# tests/test_transfer_sources.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from music_ferry.library import Library
from music_ferry.transfer import InteractiveTransfer


class TestMultiSourceTransfer:
    @pytest.fixture
    def setup_multi_source(self, tmp_path: Path):
        """Setup multi-source test environment."""
        # Create directory structure
        spotify_dir = tmp_path / "spotify"
        youtube_dir = tmp_path / "youtube"
        spotify_music = spotify_dir / "music"
        youtube_music = youtube_dir / "music"
        headphones = tmp_path / "headphones" / "Music"

        spotify_music.mkdir(parents=True)
        youtube_music.mkdir(parents=True)
        headphones.mkdir(parents=True)

        # Create libraries
        spotify_lib = Library(spotify_dir / "library.json")
        youtube_lib = Library(youtube_dir / "library.json")

        # Add tracks
        spotify_lib.add_track("sp1", "sp1.mp3", "Spotify Song", "Artist", "playlist1")
        spotify_lib.update_playlist("playlist1", "Spotify Playlist", 1)
        (spotify_music / "sp1.mp3").write_bytes(b"spotify data")

        youtube_lib.add_track(
            "yt1", "yt1.mp3", "YouTube Video", "Channel", "ytplaylist"
        )
        youtube_lib.update_playlist("ytplaylist", "YouTube Playlist", 1)
        (youtube_music / "yt1.mp3").write_bytes(b"youtube data")

        # Config mock
        config = MagicMock()
        config.paths.music_dir = tmp_path
        config.paths.headphones_mount = tmp_path / "headphones"
        config.paths.headphones_music_folder = "Music"

        return config, spotify_lib, youtube_lib, headphones

    def test_transfer_both_sources(self, setup_multi_source):
        config, spotify_lib, youtube_lib, headphones = setup_multi_source

        transfer = InteractiveTransfer(
            config,
            sources=None,  # Both sources
            spotify_library=spotify_lib,
            youtube_library=youtube_lib,
        )

        status = transfer.compute_status()

        assert status.local_track_count == 2
        assert status.new_to_transfer == 2

    def test_transfer_spotify_only(self, setup_multi_source):
        config, spotify_lib, youtube_lib, headphones = setup_multi_source

        transfer = InteractiveTransfer(
            config,
            sources=["spotify"],
            spotify_library=spotify_lib,
            youtube_library=youtube_lib,
        )

        status = transfer.compute_status()

        assert status.local_track_count == 1
        assert status.new_to_transfer == 1

    def test_transfer_youtube_only(self, setup_multi_source):
        config, spotify_lib, youtube_lib, headphones = setup_multi_source

        transfer = InteractiveTransfer(
            config,
            sources=["youtube"],
            spotify_library=spotify_lib,
            youtube_library=youtube_lib,
        )

        status = transfer.compute_status()

        assert status.local_track_count == 1
        assert status.new_to_transfer == 1

    def test_sync_copies_from_both_sources(self, setup_multi_source):
        config, spotify_lib, youtube_lib, headphones = setup_multi_source

        transfer = InteractiveTransfer(
            config,
            sources=None,
            spotify_library=spotify_lib,
            youtube_library=youtube_lib,
        )

        copied, removed = transfer.sync_changes()

        assert copied == 2
        assert (headphones / "sp1.mp3").exists()
        assert (headphones / "yt1.mp3").exists()

    def test_sync_copies_from_spotify_only(self, setup_multi_source):
        config, spotify_lib, youtube_lib, headphones = setup_multi_source

        transfer = InteractiveTransfer(
            config,
            sources=["spotify"],
            spotify_library=spotify_lib,
            youtube_library=youtube_lib,
        )

        copied, removed = transfer.sync_changes()

        assert copied == 1
        assert (headphones / "sp1.mp3").exists()
        assert not (headphones / "yt1.mp3").exists()

    def test_playlist_status_has_source_tag(self, setup_multi_source):
        config, spotify_lib, youtube_lib, headphones = setup_multi_source

        transfer = InteractiveTransfer(
            config,
            sources=None,
            spotify_library=spotify_lib,
            youtube_library=youtube_lib,
        )

        status = transfer.compute_status()

        # Check that playlists have source tags
        sources = {p.source for p in status.playlists}
        assert "spotify" in sources
        assert "youtube" in sources

    def test_full_reset_copies_from_selected_sources(self, setup_multi_source):
        config, spotify_lib, youtube_lib, headphones = setup_multi_source

        # Put an old file on headphones
        (headphones / "old.mp3").write_bytes(b"old data")

        transfer = InteractiveTransfer(
            config,
            sources=["youtube"],
            spotify_library=spotify_lib,
            youtube_library=youtube_lib,
        )

        copied = transfer.full_reset()

        assert copied == 1
        assert (headphones / "yt1.mp3").exists()
        assert not (headphones / "sp1.mp3").exists()
        assert not (headphones / "old.mp3").exists()
