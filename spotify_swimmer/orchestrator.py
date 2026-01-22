# spotify_swimmer/orchestrator.py
import asyncio
import logging
from pathlib import Path

from spotify_swimmer.config import Config, PlaylistConfig
from spotify_swimmer.library import Library
from spotify_swimmer.spotify_api import SpotifyAPI, Track
from spotify_swimmer.browser import SpotifyBrowser
from spotify_swimmer.recorder import AudioRecorder
from spotify_swimmer.tagger import tag_mp3
from spotify_swimmer.transfer import TransferManager
from spotify_swimmer.notify import Notifier, SyncResult, PlaylistResult


logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, config: Config):
        self.config = config

        # Setup library with migration support from old tracks.json
        library_path = config.paths.music_dir.parent / "library.json"
        old_tracks_path = config.paths.music_dir.parent / "tracks.json"
        self.library = Library(library_path, migrate_from=old_tracks_path)

        config.paths.music_dir.mkdir(parents=True, exist_ok=True)

    def _filter_new_tracks(self, tracks: list[Track]) -> list[Track]:
        if not self.config.behavior.skip_existing:
            return tracks
        return [t for t in tracks if not self.library.is_downloaded(t.id)]

    def _check_playlists_for_new_tracks(
        self, api: SpotifyAPI
    ) -> dict[str, list[Track]]:
        """
        Pre-scan all playlists and return only those with new tracks.
        Returns a dict mapping playlist_id -> list of new tracks.
        """
        playlists_with_new_tracks: dict[str, list[Track]] = {}

        for playlist in self.config.playlists:
            try:
                all_tracks = api.get_playlist_tracks(playlist.playlist_id)
                new_tracks = self._filter_new_tracks(all_tracks)

                if new_tracks:
                    playlists_with_new_tracks[playlist.playlist_id] = new_tracks
                    logger.info(
                        f"Playlist '{playlist.name}': {len(new_tracks)} new tracks "
                        f"(of {len(all_tracks)} total)"
                    )
                else:
                    logger.info(
                        f"Playlist '{playlist.name}': fully synced "
                        f"({len(all_tracks)} tracks)"
                    )
            except Exception as e:
                logger.error(f"Failed to check playlist '{playlist.name}': {e}")

        return playlists_with_new_tracks

    async def run(self) -> SyncResult:
        playlist_results: list[PlaylistResult] = []
        global_error: str | None = None

        api = SpotifyAPI(
            client_id=self.config.spotify.client_id,
            client_secret=self.config.spotify.client_secret,
        )

        notifier = Notifier(
            ntfy_server=self.config.notifications.ntfy_server,
            ntfy_topic=self.config.notifications.ntfy_topic,
            notify_on_success=self.config.notifications.notify_on_success,
            notify_on_failure=self.config.notifications.notify_on_failure,
        )

        # Pre-check: scan all playlists for new tracks BEFORE starting browser
        logger.info("Checking playlists for new tracks...")
        playlists_with_new_tracks = self._check_playlists_for_new_tracks(api)

        if not playlists_with_new_tracks:
            logger.info("All playlists are fully synced. Nothing to do.")
            # Report all playlists as synced with 0 new tracks
            for playlist in self.config.playlists:
                playlist_results.append(
                    PlaylistResult(name=playlist.name, tracks_synced=0, error=None)
                )
            result = SyncResult(
                playlists=playlist_results,
                transferred=False,
                global_error=None,
            )
            # Still notify on success if configured
            notifier.send(result)
            return result

        total_new = sum(len(tracks) for tracks in playlists_with_new_tracks.values())
        logger.info(
            f"Found {total_new} new tracks across "
            f"{len(playlists_with_new_tracks)} playlists. Starting sync..."
        )

        try:
            with AudioRecorder(bitrate=self.config.audio.bitrate) as recorder:
                async with SpotifyBrowser(
                    cookies_dir=self.config.paths.music_dir.parent / "cookies",
                    audio_sink=recorder.sink_name,
                ) as browser:
                    if not await browser.is_logged_in():
                        global_error = "Login expired - please re-authenticate"
                        raise RuntimeError(global_error)

                    for playlist in self.config.playlists:
                        # Only process playlists that have new tracks
                        new_tracks = playlists_with_new_tracks.get(
                            playlist.playlist_id
                        )
                        if new_tracks:
                            result = await self._sync_playlist_tracks(
                                playlist, new_tracks, browser, recorder
                            )
                        else:
                            # Playlist was already fully synced
                            result = PlaylistResult(
                                name=playlist.name, tracks_synced=0, error=None
                            )
                        playlist_results.append(result)

        except RuntimeError as e:
            global_error = str(e)
            for playlist in self.config.playlists:
                if not any(r.name == playlist.name for r in playlist_results):
                    playlist_results.append(
                        PlaylistResult(name=playlist.name, tracks_synced=0, error=str(e))
                    )

        transferred = False
        if self.config.behavior.auto_transfer:
            try:
                transfer_manager = TransferManager(
                    headphones_mount=self.config.paths.headphones_mount,
                    headphones_music_folder=self.config.paths.headphones_music_folder,
                )
                if transfer_manager.is_mounted():
                    transfer_manager.transfer(self.config.paths.music_dir)
                    transferred = True
                else:
                    logger.warning("Headphones not mounted, skipping transfer")
            except Exception as e:
                logger.error(f"Transfer failed: {e}")

        result = SyncResult(
            playlists=playlist_results,
            transferred=transferred,
            global_error=global_error,
        )

        notifier.send(result)
        return result

    async def _sync_playlist_tracks(
        self,
        playlist: PlaylistConfig,
        tracks: list[Track],
        browser: SpotifyBrowser,
        recorder: AudioRecorder,
    ) -> PlaylistResult:
        """Sync pre-fetched tracks for a playlist."""
        try:
            logger.info(f"Playlist '{playlist.name}': syncing {len(tracks)} tracks")

            synced_count = 0
            for track in tracks:
                try:
                    await self._record_track(track, browser, recorder)
                    synced_count += 1
                except Exception as e:
                    logger.error(f"Failed to record {track.name}: {e}")

            return PlaylistResult(
                name=playlist.name,
                tracks_synced=synced_count,
                error=None,
            )

        except Exception as e:
            logger.error(f"Failed to sync playlist {playlist.name}: {e}")
            return PlaylistResult(
                name=playlist.name,
                tracks_synced=0,
                error=str(e),
            )

    async def _record_track(
        self,
        track: Track,
        browser: SpotifyBrowser,
        recorder: AudioRecorder,
    ) -> None:
        output_path = self.config.paths.music_dir / f"{track.id}.mp3"

        logger.info(f"Recording: {track.name} by {track.artist_string}")

        await browser.play_track(track.id)
        await asyncio.sleep(2)

        recorder.start_recording(output_path)
        await asyncio.sleep(track.duration_seconds + 2)
        recorder.stop_recording()

        await browser.pause()

        tag_mp3(output_path, track)
        # Note: playlist_id will be added by _update_playlist_membership
        self.library.add_track(
            track.id, f"{track.id}.mp3", track.name, track.artist_string, ""
        )

        logger.info(f"Completed: {track.name}")
