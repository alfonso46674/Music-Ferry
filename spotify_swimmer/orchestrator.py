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

    def _cleanup_orphaned_tracks(self) -> int:
        """Delete orphaned tracks from disk and library. Returns count deleted."""
        orphaned = self.library.get_orphaned_tracks()
        deleted_count = 0

        for track in orphaned:
            mp3_path = self.config.paths.music_dir / track.filename

            # Delete MP3 file if exists
            if mp3_path.exists():
                mp3_path.unlink()
                logger.info(f"Deleted orphaned file: {track.filename}")

            # Remove from library
            self.library.delete_track(track.id)
            deleted_count += 1
            logger.info(f"Removed orphaned track: {track.title} by {track.artist}")

        return deleted_count

    def _update_playlist_membership(
        self,
        playlist_id: str,
        playlist_name: str,
        api_tracks: list[Track],
    ) -> None:
        """Update library to reflect current playlist membership from API."""
        api_track_ids = {t.id for t in api_tracks}

        # Update playlist metadata
        self.library.update_playlist(playlist_id, playlist_name, len(api_tracks))

        # Add playlist to tracks that are in API response and already downloaded
        for track in api_tracks:
            if self.library.is_downloaded(track.id):
                self.library.add_track_to_playlist(track.id, playlist_id)

        # Remove playlist from tracks no longer in API response
        for lib_track in self.library.get_tracks_for_playlist(playlist_id):
            if lib_track.id not in api_track_ids:
                self.library.remove_track_from_playlist(lib_track.id, playlist_id)

    def _fetch_all_playlists(self, api: SpotifyAPI) -> dict[str, list[Track]]:
        """Fetch all tracks for all playlists. Returns dict mapping playlist_id -> tracks."""
        all_playlist_tracks: dict[str, list[Track]] = {}

        for playlist in self.config.playlists:
            try:
                tracks = api.get_playlist_tracks(playlist.playlist_id)
                all_playlist_tracks[playlist.playlist_id] = tracks
                logger.debug(f"Fetched {len(tracks)} tracks from '{playlist.name}'")
            except Exception as e:
                logger.error(f"Failed to fetch playlist '{playlist.name}': {e}")
                all_playlist_tracks[playlist.playlist_id] = []

        return all_playlist_tracks

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

        # Fetch all playlist tracks from API
        logger.info("Fetching playlist data from Spotify...")
        all_playlist_tracks = self._fetch_all_playlists(api)

        # Determine which playlists have new tracks
        playlists_with_new_tracks: dict[str, list[Track]] = {}
        for playlist in self.config.playlists:
            all_tracks = all_playlist_tracks.get(playlist.playlist_id, [])
            new_tracks = self._filter_new_tracks(all_tracks)
            if new_tracks:
                playlists_with_new_tracks[playlist.playlist_id] = new_tracks
                logger.info(
                    f"Playlist '{playlist.name}': {len(new_tracks)} new tracks "
                    f"(of {len(all_tracks)} total)"
                )
            else:
                logger.info(
                    f"Playlist '{playlist.name}': fully synced ({len(all_tracks)} tracks)"
                )

        # Download new tracks if any exist
        if playlists_with_new_tracks:
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
                            new_tracks = playlists_with_new_tracks.get(playlist.playlist_id)
                            if new_tracks:
                                result = await self._sync_playlist_tracks(
                                    playlist, new_tracks, browser, recorder
                                )
                            else:
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
        else:
            logger.info("All playlists are fully synced. No downloads needed.")
            for playlist in self.config.playlists:
                playlist_results.append(
                    PlaylistResult(name=playlist.name, tracks_synced=0, error=None)
                )

        # Update playlist membership for all playlists
        logger.info("Updating playlist membership...")
        for playlist in self.config.playlists:
            all_tracks = all_playlist_tracks.get(playlist.playlist_id, [])
            self._update_playlist_membership(
                playlist.playlist_id, playlist.name, all_tracks
            )

        # Cleanup orphaned tracks
        orphans_deleted = self._cleanup_orphaned_tracks()
        if orphans_deleted > 0:
            logger.info(f"Cleaned up {orphans_deleted} orphaned tracks")

        # Never transfer - that's a separate command now
        result = SyncResult(
            playlists=playlist_results,
            transferred=False,
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
