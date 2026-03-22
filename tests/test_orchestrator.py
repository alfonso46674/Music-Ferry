# tests/test_orchestrator.py
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from music_ferry.config import (
    AudioConfig,
    BehaviorConfig,
    Config,
    NotificationsConfig,
    PathsConfig,
    PlaylistConfig,
    SpotifyConfig,
    TransferConfig,
    YouTubeConfig,
)
from music_ferry.orchestrator import Orchestrator
from music_ferry.spotify_api import Track


@pytest.fixture
def sample_config(tmp_path: Path) -> Config:
    return Config(
        spotify=SpotifyConfig(
            client_id="test_id",
            client_secret="test_secret",
            username="test_user",
            enabled=True,
            playlists=[
                PlaylistConfig(
                    name="Test Playlist", url="https://open.spotify.com/playlist/abc123"
                ),
            ],
        ),
        youtube=YouTubeConfig(enabled=False, playlists=[]),
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
            trim_silence=True,
        ),
        transfer=TransferConfig(reserve_free_gb=0.0),
    )


class TestOrchestrator:
    def test_filter_new_tracks(self, sample_config: Config, tmp_path: Path):
        orchestrator = Orchestrator(sample_config)
        orchestrator.spotify_library.add_track(
            "existing123", "existing123.mp3", "Old Song", "A", "playlist1"
        )

        tracks = [
            Track(
                id="existing123",
                name="Old Song",
                artists=["A"],
                album="B",
                duration_ms=180000,
                album_art_url=None,
            ),
            Track(
                id="new456",
                name="New Song",
                artists=["C"],
                album="D",
                duration_ms=200000,
                album_art_url=None,
            ),
        ]

        new_tracks = orchestrator._filter_new_tracks(
            tracks, orchestrator.spotify_library
        )

        assert len(new_tracks) == 1
        assert new_tracks[0].id == "new456"

    def test_orchestrator_uses_library(self, sample_config: Config, tmp_path: Path):
        from music_ferry.library import Library

        orchestrator = Orchestrator(sample_config)
        assert isinstance(orchestrator.spotify_library, Library)
        assert isinstance(orchestrator.youtube_library, Library)

    def test_orchestrator_migrates_old_db(self, sample_config: Config, tmp_path: Path):
        import json

        # Create old tracks.json
        old_db = sample_config.paths.music_dir.parent / "tracks.json"
        old_db.parent.mkdir(parents=True, exist_ok=True)
        old_db.write_text(json.dumps({"track1": "track1.mp3"}))

        orchestrator = Orchestrator(sample_config)
        assert orchestrator.spotify_library.is_downloaded("track1")

    def test_cleanup_orphaned_tracks(self, sample_config: Config, tmp_path: Path):
        orchestrator = Orchestrator(sample_config)

        # Add a track to a playlist, then remove it (making it orphaned)
        orchestrator.spotify_library.add_track(
            "orphan1", "orphan1.mp3", "Orphan Song", "Artist", "playlist1"
        )
        orchestrator.spotify_library.remove_track_from_playlist("orphan1", "playlist1")

        # Create the MP3 file
        mp3_path = orchestrator.spotify_music_dir / "orphan1.mp3"
        mp3_path.write_bytes(b"fake mp3 data")

        deleted = orchestrator._cleanup_orphaned_tracks(
            orchestrator.spotify_library, orchestrator.spotify_music_dir
        )

        assert deleted == 1
        assert not mp3_path.exists()
        assert not orchestrator.spotify_library.is_downloaded("orphan1")

    def test_cleanup_orphaned_tracks_keeps_non_orphans(
        self, sample_config: Config, tmp_path: Path
    ):
        orchestrator = Orchestrator(sample_config)

        # Add a track that's NOT orphaned
        orchestrator.spotify_library.add_track(
            "active1", "active1.mp3", "Active Song", "Artist", "playlist1"
        )

        # Create the MP3 file
        mp3_path = orchestrator.spotify_music_dir / "active1.mp3"
        mp3_path.write_bytes(b"fake mp3 data")

        deleted = orchestrator._cleanup_orphaned_tracks(
            orchestrator.spotify_library, orchestrator.spotify_music_dir
        )

        assert deleted == 0
        assert mp3_path.exists()
        assert orchestrator.spotify_library.is_downloaded("active1")

    def test_update_playlist_membership_adds_new_playlist(
        self, sample_config: Config, tmp_path: Path
    ):
        orchestrator = Orchestrator(sample_config)

        # Create a track that's in library for playlist1
        orchestrator.spotify_library.add_track(
            "track1", "track1.mp3", "Song 1", "Artist", "playlist1"
        )

        # Simulate track appearing in playlist2 as well (from API)
        mock_tracks = [
            Track(
                id="track1",
                name="Song 1",
                artists=["Artist"],
                album="Album",
                duration_ms=180000,
                album_art_url=None,
            )
        ]

        orchestrator._update_playlist_membership(
            "playlist2", "Playlist 2", mock_tracks, orchestrator.spotify_library
        )

        track = orchestrator.spotify_library.get_track("track1")
        assert "playlist1" in track.playlists
        assert "playlist2" in track.playlists

    def test_update_playlist_membership_removes_old_tracks(
        self, sample_config: Config, tmp_path: Path
    ):
        orchestrator = Orchestrator(sample_config)

        # Create tracks in playlist1
        orchestrator.spotify_library.add_track(
            "track1", "track1.mp3", "Song 1", "Artist", "playlist1"
        )
        orchestrator.spotify_library.add_track(
            "track2", "track2.mp3", "Song 2", "Artist", "playlist1"
        )

        # API now only has track1 in playlist1 (track2 was removed)
        mock_tracks = [
            Track(
                id="track1",
                name="Song 1",
                artists=["Artist"],
                album="Album",
                duration_ms=180000,
                album_art_url=None,
            )
        ]

        orchestrator._update_playlist_membership(
            "playlist1", "Playlist 1", mock_tracks, orchestrator.spotify_library
        )

        # track1 should still be in playlist1
        track1 = orchestrator.spotify_library.get_track("track1")
        assert "playlist1" in track1.playlists

        # track2 should no longer be in playlist1 (now orphaned)
        track2 = orchestrator.spotify_library.get_track("track2")
        assert "playlist1" not in track2.playlists
        assert track2.is_orphaned


class TestPlaybackModeSelection:
    def test_playlist_mode_when_mostly_new(self):
        # 8 new out of 10 = 80% > 70% threshold
        mode = Orchestrator._select_playback_mode(new_count=8, total_count=10)
        assert mode == "playlist"

    def test_individual_mode_when_few_new(self):
        # 2 new out of 10 = 20% < 70% threshold
        mode = Orchestrator._select_playback_mode(new_count=2, total_count=10)
        assert mode == "individual"

    def test_playlist_mode_at_threshold(self):
        # 7 new out of 10 = 70% = threshold
        mode = Orchestrator._select_playback_mode(new_count=7, total_count=10)
        assert mode == "playlist"

    def test_individual_mode_below_threshold(self):
        # 6 new out of 10 = 60% < 70%
        mode = Orchestrator._select_playback_mode(new_count=6, total_count=10)
        assert mode == "individual"

    def test_playlist_mode_when_all_new(self):
        mode = Orchestrator._select_playback_mode(new_count=10, total_count=10)
        assert mode == "playlist"

    def test_individual_mode_when_empty_playlist(self):
        mode = Orchestrator._select_playback_mode(new_count=0, total_count=0)
        assert mode == "individual"


class TestPlaylistModeRecording:
    @pytest.mark.asyncio
    async def test_record_playlist_mode_records_only_new(
        self, sample_config: Config, tmp_path: Path
    ):
        from music_ferry.library import Library

        # Setup library with one existing track
        lib = Library(tmp_path / "library.json")
        lib.add_track("existing1", "existing1.mp3", "Existing", "Artist", "playlist1")

        orchestrator = Orchestrator.__new__(Orchestrator)
        orchestrator.config = sample_config
        orchestrator.spotify_library = lib
        orchestrator.spotify_music_dir = tmp_path / "music"

        all_tracks = [
            Track(
                id="existing1",
                name="Existing",
                artists=["Artist"],
                album="Album",
                duration_ms=180000,
                album_art_url=None,
            ),
            Track(
                id="new1",
                name="New Song",
                artists=["Artist"],
                album="Album",
                duration_ms=200000,
                album_art_url=None,
            ),
        ]
        new_track_ids = {"new1"}

        mock_browser = MagicMock()
        # Track changes from existing1 -> new1 -> None (end of playlist)
        mock_browser.get_current_track_id.return_value = "existing1"
        mock_browser.play_playlist = AsyncMock()
        mock_browser.wait_for_track_change = AsyncMock(side_effect=["new1", None])

        mock_recorder = MagicMock()

        with patch.object(
            orchestrator, "_record_current_track", new_callable=AsyncMock
        ) as mock_record:
            await orchestrator._record_playlist_mode(
                playlist_id="playlist1",
                all_tracks=all_tracks,
                new_track_ids=new_track_ids,
                browser=mock_browser,
                recorder=mock_recorder,
            )

        # Should only record the new track (not existing1)
        assert mock_record.call_count == 1
        # The recorded track should be new1
        assert mock_record.call_args[0][0].id == "new1"

    @pytest.mark.asyncio
    async def test_record_playlist_mode_stops_at_playlist_end(
        self, sample_config: Config, tmp_path: Path
    ):
        from music_ferry.library import Library

        lib = Library(tmp_path / "library.json")
        orchestrator = Orchestrator.__new__(Orchestrator)
        orchestrator.config = sample_config
        orchestrator.spotify_library = lib
        orchestrator.spotify_music_dir = tmp_path / "music"

        all_tracks = [
            Track(
                id="track1",
                name="Song 1",
                artists=["Artist"],
                album="Album",
                duration_ms=180000,
                album_art_url=None,
            ),
        ]

        mock_browser = MagicMock()
        mock_browser.get_current_track_id.return_value = "track1"
        mock_browser.play_playlist = AsyncMock()
        mock_browser.wait_for_track_change = AsyncMock(
            return_value=None
        )  # Playlist ends

        mock_recorder = MagicMock()

        with patch.object(
            orchestrator, "_record_current_track", new_callable=AsyncMock
        ) as mock_record:
            recorded = await orchestrator._record_playlist_mode(
                playlist_id="playlist1",
                all_tracks=all_tracks,
                new_track_ids={"track1"},
                browser=mock_browser,
                recorder=mock_recorder,
            )

        assert mock_record.call_count == 1
        assert recorded == 1


class TestOrchestratorSync:
    @pytest.mark.asyncio
    @patch("music_ferry.orchestrator.tag_mp3")
    @patch("music_ferry.orchestrator.asyncio.sleep", new_callable=AsyncMock)
    @patch("music_ferry.orchestrator.SpotifyAPI")
    @patch("music_ferry.orchestrator.SpotifyBrowser")
    @patch("music_ferry.orchestrator.AudioRecorder")
    @patch("music_ferry.orchestrator.Notifier")
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
            Track(
                id="track1",
                name="Song 1",
                artists=["Artist"],
                album="Album",
                duration_ms=180000,
                album_art_url=None,
            ),
        ]
        mock_api_class.return_value = mock_api

        mock_browser = MagicMock()
        mock_browser.__aenter__ = AsyncMock(return_value=mock_browser)
        mock_browser.__aexit__ = AsyncMock(return_value=None)
        mock_browser.is_logged_in = AsyncMock(return_value=True)
        mock_browser.play_playlist = AsyncMock()
        mock_browser.play_track = AsyncMock()
        # With 100% new tracks, playlist mode is used - mock track detection
        mock_browser.get_current_track_id.return_value = "track1"
        mock_browser.wait_for_track_change = AsyncMock(
            return_value=None
        )  # End of playlist
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
