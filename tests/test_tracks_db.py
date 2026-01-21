# tests/test_tracks_db.py
from pathlib import Path

import pytest

from spotify_swimmer.tracks_db import TracksDB


class TestTracksDB:
    def test_empty_database(self, tmp_path: Path):
        db = TracksDB(tmp_path / "tracks.json")
        assert db.is_downloaded("abc123") is False

    def test_add_and_check_track(self, tmp_path: Path):
        db = TracksDB(tmp_path / "tracks.json")
        db.add_track("abc123", "abc123.mp3")
        assert db.is_downloaded("abc123") is True

    def test_get_filename(self, tmp_path: Path):
        db = TracksDB(tmp_path / "tracks.json")
        db.add_track("abc123", "abc123.mp3")
        assert db.get_filename("abc123") == "abc123.mp3"

    def test_persistence(self, tmp_path: Path):
        db_path = tmp_path / "tracks.json"

        db1 = TracksDB(db_path)
        db1.add_track("abc123", "abc123.mp3")
        db1.save()

        db2 = TracksDB(db_path)
        assert db2.is_downloaded("abc123") is True
        assert db2.get_filename("abc123") == "abc123.mp3"

    def test_list_all_tracks(self, tmp_path: Path):
        db = TracksDB(tmp_path / "tracks.json")
        db.add_track("abc123", "abc123.mp3")
        db.add_track("def456", "def456.mp3")

        tracks = db.list_tracks()
        assert len(tracks) == 2
        assert "abc123" in tracks
        assert "def456" in tracks

    def test_remove_track(self, tmp_path: Path):
        db = TracksDB(tmp_path / "tracks.json")
        db.add_track("abc123", "abc123.mp3")
        db.remove_track("abc123")
        assert db.is_downloaded("abc123") is False
