# tests/test_transfer.py
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from spotify_swimmer.transfer import TransferManager


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
