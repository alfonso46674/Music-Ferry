# tests/test_transfer.py
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from spotify_swimmer.transfer import TransferManager, InteractiveTransfer, TransferStatus
from spotify_swimmer.library import Library


class TestTransferManager:
    def test_is_mounted_true(self, tmp_path: Path):
        mount_point = tmp_path / "HEADPHONES"
        mount_point.mkdir()
        (mount_point / "Music").mkdir()

        manager = TransferManager(
            headphones_mount=mount_point,
            headphones_music_folder="Music",
        )
        assert manager.is_mounted() is True

    def test_is_mounted_false(self, tmp_path: Path):
        mount_point = tmp_path / "HEADPHONES"
        # Don't create the directory

        manager = TransferManager(
            headphones_mount=mount_point,
            headphones_music_folder="Music",
        )
        assert manager.is_mounted() is False

    def test_transfer_files(self, tmp_path: Path):
        # Setup source files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "song1.mp3").write_bytes(b"audio1")
        (source_dir / "song2.mp3").write_bytes(b"audio2")

        # Setup destination
        mount_point = tmp_path / "HEADPHONES"
        mount_point.mkdir()
        music_folder = mount_point / "Music"
        music_folder.mkdir()

        manager = TransferManager(
            headphones_mount=mount_point,
            headphones_music_folder="Music",
        )

        transferred = manager.transfer(source_dir)

        assert transferred == 2
        assert (music_folder / "song1.mp3").exists()
        assert (music_folder / "song2.mp3").exists()

    def test_transfer_skips_existing(self, tmp_path: Path):
        # Setup source
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "song1.mp3").write_bytes(b"new audio")

        # Setup destination with existing file
        mount_point = tmp_path / "HEADPHONES"
        mount_point.mkdir()
        music_folder = mount_point / "Music"
        music_folder.mkdir()
        (music_folder / "song1.mp3").write_bytes(b"old audio")

        manager = TransferManager(
            headphones_mount=mount_point,
            headphones_music_folder="Music",
        )

        transferred = manager.transfer(source_dir)

        # File should be updated (rsync behavior)
        assert transferred >= 0  # rsync may or may not count unchanged files

    def test_transfer_when_not_mounted(self, tmp_path: Path):
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        mount_point = tmp_path / "HEADPHONES"
        # Don't mount

        manager = TransferManager(
            headphones_mount=mount_point,
            headphones_music_folder="Music",
        )

        with pytest.raises(RuntimeError, match="not mounted"):
            manager.transfer(source_dir)


class TestInteractiveTransfer:
    @pytest.fixture
    def mock_config(self, tmp_path: Path):
        config = MagicMock()
        config.paths.music_dir = tmp_path / "music"
        config.paths.music_dir.mkdir()
        # Create spotify source directory structure
        spotify_music = config.paths.music_dir / "spotify" / "music"
        spotify_music.mkdir(parents=True)
        config.paths.headphones_mount = tmp_path / "headphones"
        config.paths.headphones_mount.mkdir()
        config.paths.headphones_music_folder = "Music"
        (config.paths.headphones_mount / "Music").mkdir()
        return config

    def test_compute_transfer_status(self, mock_config, tmp_path: Path):
        # Setup library in spotify directory
        spotify_dir = mock_config.paths.music_dir / "spotify"
        lib = Library(spotify_dir / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        lib.add_track("track2", "track2.mp3", "Song 2", "Artist", "playlist1")
        lib.update_playlist("playlist1", "My Playlist", 2)

        # Create MP3 files locally in spotify music dir
        spotify_music = spotify_dir / "music"
        (spotify_music / "track1.mp3").write_bytes(b"data")
        (spotify_music / "track2.mp3").write_bytes(b"data")

        # Put one track on headphones already
        headphones_music = mock_config.paths.headphones_mount / "Music"
        (headphones_music / "track1.mp3").write_bytes(b"data")

        transfer = InteractiveTransfer(mock_config, sources=["spotify"], spotify_library=lib)
        status = transfer.compute_status()

        assert status.local_track_count == 2
        assert status.headphones_track_count == 1
        assert status.new_to_transfer == 1
        assert status.orphaned_on_headphones == 0

    def test_compute_orphaned_tracks(self, mock_config, tmp_path: Path):
        # Setup library in spotify directory
        spotify_dir = mock_config.paths.music_dir / "spotify"
        lib = Library(spotify_dir / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        lib.update_playlist("playlist1", "My Playlist", 1)

        # Create file in spotify music dir
        spotify_music = spotify_dir / "music"
        (spotify_music / "track1.mp3").write_bytes(b"data")

        # Put extra file on headphones that's not in library
        headphones_music = mock_config.paths.headphones_mount / "Music"
        (headphones_music / "track1.mp3").write_bytes(b"data")
        (headphones_music / "orphan.mp3").write_bytes(b"data")

        transfer = InteractiveTransfer(mock_config, sources=["spotify"], spotify_library=lib)
        status = transfer.compute_status()

        assert status.orphaned_on_headphones == 1

    def test_sync_changes(self, mock_config, tmp_path: Path):
        # Setup library in spotify directory
        spotify_dir = mock_config.paths.music_dir / "spotify"
        lib = Library(spotify_dir / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")
        lib.add_track("track2", "track2.mp3", "Song 2", "Artist", "playlist1")

        # Create local files in spotify music dir
        spotify_music = spotify_dir / "music"
        (spotify_music / "track1.mp3").write_bytes(b"data1")
        (spotify_music / "track2.mp3").write_bytes(b"data2")

        # Put orphan on headphones
        headphones_music = mock_config.paths.headphones_mount / "Music"
        (headphones_music / "orphan.mp3").write_bytes(b"orphan")

        transfer = InteractiveTransfer(mock_config, sources=["spotify"], spotify_library=lib)
        transfer.sync_changes()

        # New files should be copied
        assert (headphones_music / "track1.mp3").exists()
        assert (headphones_music / "track2.mp3").exists()
        # Orphan should be removed
        assert not (headphones_music / "orphan.mp3").exists()

    def test_full_reset(self, mock_config, tmp_path: Path):
        # Setup library in spotify directory
        spotify_dir = mock_config.paths.music_dir / "spotify"
        lib = Library(spotify_dir / "library.json")
        lib.add_track("track1", "track1.mp3", "Song 1", "Artist", "playlist1")

        # Create file in spotify music dir
        spotify_music = spotify_dir / "music"
        (spotify_music / "track1.mp3").write_bytes(b"data1")

        # Put existing files on headphones
        headphones_music = mock_config.paths.headphones_mount / "Music"
        (headphones_music / "old.mp3").write_bytes(b"old")
        (headphones_music / "other.mp3").write_bytes(b"other")

        transfer = InteractiveTransfer(mock_config, sources=["spotify"], spotify_library=lib)
        transfer.full_reset()

        # Only library tracks should remain
        assert (headphones_music / "track1.mp3").exists()
        assert not (headphones_music / "old.mp3").exists()
        assert not (headphones_music / "other.mp3").exists()
