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
from spotify_swimmer.youtube import YouTubeDownloader


logger = logging.getLogger(__name__)

PLAYLIST_MODE_THRESHOLD = 0.7  # Use playlist mode when >= 70% of tracks are new


class Orchestrator:
    def __init__(self, config: Config):
        self.config = config

        # Setup directories for each source
        spotify_base = config.paths.music_dir / "spotify"
        youtube_base = config.paths.music_dir / "youtube"

        spotify_base.mkdir(parents=True, exist_ok=True)
        youtube_base.mkdir(parents=True, exist_ok=True)
        (spotify_base / "music").mkdir(exist_ok=True)
        (youtube_base / "music").mkdir(exist_ok=True)

        # Setup libraries with migration support
        old_library = config.paths.music_dir.parent / "library.json"
        old_tracks_path = config.paths.music_dir.parent / "tracks.json"

        # Migrate from old library.json or tracks.json if exists
        migrate_from = None
        if old_library.exists():
            migrate_from = old_library
        elif old_tracks_path.exists():
            migrate_from = old_tracks_path

        self.spotify_library = Library(
            spotify_base / "library.json",
            migrate_from=migrate_from,
        )
        self.youtube_library = Library(youtube_base / "library.json")

        # Paths for music storage
        self.spotify_music_dir = spotify_base / "music"
        self.youtube_music_dir = youtube_base / "music"

    def _filter_new_tracks(self, tracks: list[Track], library: Library) -> list[Track]:
        if not self.config.behavior.skip_existing:
            return tracks
        return [t for t in tracks if not library.is_downloaded(t.id)]

    @staticmethod
    def _select_playback_mode(new_count: int, total_count: int) -> str:
        """Select playback mode based on ratio of new tracks.

        Returns 'playlist' if >= 70% of tracks are new (looks more natural),
        otherwise returns 'individual' for targeted downloads.
        """
        if total_count == 0:
            return "individual"
        ratio = new_count / total_count
        if ratio >= PLAYLIST_MODE_THRESHOLD:
            return "playlist"
        return "individual"

    def _cleanup_orphaned_tracks(self, library: Library, music_dir: Path) -> int:
        """Delete orphaned tracks from disk and library. Returns count deleted."""
        orphaned = library.get_orphaned_tracks()
        deleted_count = 0

        for track in orphaned:
            mp3_path = music_dir / track.filename

            # Delete MP3 file if exists
            if mp3_path.exists():
                mp3_path.unlink()
                logger.info(f"Deleted orphaned file: {track.filename}")

            # Remove from library
            library.delete_track(track.id)
            deleted_count += 1
            logger.info(f"Removed orphaned track: {track.title} by {track.artist}")

        return deleted_count

    def _update_playlist_membership(
        self,
        playlist_id: str,
        playlist_name: str,
        api_tracks: list[Track],
        library: Library,
    ) -> None:
        """Update library to reflect current playlist membership from API."""
        api_track_ids = {t.id for t in api_tracks}

        # Update playlist metadata
        library.update_playlist(playlist_id, playlist_name, len(api_tracks))

        # Add playlist to tracks that are in API response and already downloaded
        for track in api_tracks:
            if library.is_downloaded(track.id):
                library.add_track_to_playlist(track.id, playlist_id)

        # Remove playlist from tracks no longer in API response
        for lib_track in library.get_tracks_for_playlist(playlist_id):
            if lib_track.id not in api_track_ids:
                library.remove_track_from_playlist(lib_track.id, playlist_id)

    def _fetch_all_playlists(self, api: SpotifyAPI) -> dict[str, list[Track]]:
        """Fetch all tracks for all playlists. Returns dict mapping playlist_id -> tracks."""
        all_playlist_tracks: dict[str, list[Track]] = {}

        for playlist in self.config.spotify.playlists:
            try:
                tracks = api.get_playlist_tracks(playlist.playlist_id)
                all_playlist_tracks[playlist.playlist_id] = tracks
                logger.debug(f"Fetched {len(tracks)} tracks from '{playlist.name}'")
            except Exception as e:
                logger.error(f"Failed to fetch playlist '{playlist.name}': {e}")
                all_playlist_tracks[playlist.playlist_id] = []

        return all_playlist_tracks

    async def run(
        self,
        sync_spotify: bool = True,
        sync_youtube: bool = True,
    ) -> SyncResult:
        """Run sync for selected sources."""
        playlist_results: list[PlaylistResult] = []
        global_error: str | None = None

        notifier = Notifier(
            ntfy_server=self.config.notifications.ntfy_server,
            ntfy_topic=self.config.notifications.ntfy_topic,
            notify_on_success=self.config.notifications.notify_on_success,
            notify_on_failure=self.config.notifications.notify_on_failure,
        )

        try:
            if sync_spotify and self.config.spotify.enabled:
                spotify_results = await self._sync_spotify()
                playlist_results.extend(spotify_results)

            if sync_youtube and self.config.youtube.enabled:
                youtube_results = await self._sync_youtube()
                playlist_results.extend(youtube_results)

        except Exception as e:
            global_error = str(e)

        # Never transfer - that's a separate command now
        result = SyncResult(
            playlists=playlist_results,
            transferred=False,
            global_error=global_error,
        )

        notifier.send(result)
        return result

    async def _sync_spotify(self) -> list[PlaylistResult]:
        """Sync Spotify playlists using browser recording."""
        playlist_results: list[PlaylistResult] = []

        if not self.config.spotify.playlists:
            logger.info("No Spotify playlists configured")
            return playlist_results

        api = SpotifyAPI(
            client_id=self.config.spotify.client_id,
            client_secret=self.config.spotify.client_secret,
        )

        # Fetch all playlist tracks from API
        logger.info("Fetching playlist data from Spotify...")
        all_playlist_tracks = self._fetch_all_playlists(api)

        # Determine which playlists have new tracks
        playlists_with_new_tracks: dict[str, list[Track]] = {}
        for playlist in self.config.spotify.playlists:
            all_tracks = all_playlist_tracks.get(playlist.playlist_id, [])
            new_tracks = self._filter_new_tracks(all_tracks, self.spotify_library)
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
                            raise RuntimeError("Login expired - please re-authenticate")

                        for playlist in self.config.spotify.playlists:
                            new_tracks = playlists_with_new_tracks.get(playlist.playlist_id)
                            all_tracks = all_playlist_tracks.get(playlist.playlist_id, [])
                            if new_tracks:
                                result = await self._sync_playlist_tracks(
                                    playlist, new_tracks, all_tracks, browser, recorder
                                )
                            else:
                                result = PlaylistResult(
                                    name=playlist.name, tracks_synced=0, error=None
                                )
                            playlist_results.append(result)

            except RuntimeError as e:
                for playlist in self.config.spotify.playlists:
                    if not any(r.name == playlist.name for r in playlist_results):
                        playlist_results.append(
                            PlaylistResult(name=playlist.name, tracks_synced=0, error=str(e))
                        )
        else:
            logger.info("All Spotify playlists are fully synced. No downloads needed.")
            for playlist in self.config.spotify.playlists:
                playlist_results.append(
                    PlaylistResult(name=playlist.name, tracks_synced=0, error=None)
                )

        # Update playlist membership for all playlists
        logger.info("Updating Spotify playlist membership...")
        for playlist in self.config.spotify.playlists:
            all_tracks = all_playlist_tracks.get(playlist.playlist_id, [])
            self._update_playlist_membership(
                playlist.playlist_id, playlist.name, all_tracks, self.spotify_library
            )

        # Cleanup orphaned tracks
        orphans_deleted = self._cleanup_orphaned_tracks(
            self.spotify_library, self.spotify_music_dir
        )
        if orphans_deleted > 0:
            logger.info(f"Cleaned up {orphans_deleted} orphaned Spotify tracks")

        return playlist_results

    async def _sync_youtube(self) -> list[PlaylistResult]:
        """Sync YouTube playlists using yt-dlp."""
        playlist_results: list[PlaylistResult] = []

        if not self.config.youtube.playlists:
            logger.info("No YouTube playlists configured")
            return playlist_results

        downloader = YouTubeDownloader(
            output_dir=self.youtube_music_dir,
            bitrate=self.config.audio.bitrate,
        )

        for playlist in self.config.youtube.playlists:
            try:
                logger.info(f"Fetching YouTube playlist: {playlist.name}")
                all_tracks = downloader.get_playlist_tracks(
                    playlist.url, playlist.name
                )

                new_tracks = self._filter_new_tracks(all_tracks, self.youtube_library)

                if new_tracks:
                    logger.info(f"YouTube '{playlist.name}': {len(new_tracks)} new tracks")
                    downloaded = downloader.download_tracks(new_tracks)

                    # Add downloaded tracks to library
                    for track in new_tracks[:downloaded]:
                        self.youtube_library.add_track(
                            track.id,
                            f"{track.id}.mp3",
                            track.name,
                            track.artist_string,
                            playlist.playlist_id,
                        )

                    playlist_results.append(
                        PlaylistResult(name=playlist.name, tracks_synced=downloaded, error=None)
                    )
                else:
                    logger.info(f"YouTube '{playlist.name}': fully synced")
                    playlist_results.append(
                        PlaylistResult(name=playlist.name, tracks_synced=0, error=None)
                    )

                # Update playlist membership
                self._update_playlist_membership(
                    playlist.playlist_id, playlist.name, all_tracks, self.youtube_library
                )

            except Exception as e:
                logger.error(f"Failed to sync YouTube playlist: {e}")
                playlist_results.append(
                    PlaylistResult(name=playlist.name, tracks_synced=0, error=str(e))
                )

        # Cleanup orphaned tracks
        orphans_deleted = self._cleanup_orphaned_tracks(
            self.youtube_library, self.youtube_music_dir
        )
        if orphans_deleted > 0:
            logger.info(f"Cleaned up {orphans_deleted} orphaned YouTube tracks")

        return playlist_results

    async def _sync_playlist_tracks(
        self,
        playlist: PlaylistConfig,
        new_tracks: list[Track],
        all_tracks: list[Track],
        browser: SpotifyBrowser,
        recorder: AudioRecorder,
    ) -> PlaylistResult:
        """Sync tracks for a playlist using appropriate playback mode."""
        try:
            mode = self._select_playback_mode(len(new_tracks), len(all_tracks))
            logger.info(
                f"Playlist '{playlist.name}': {len(new_tracks)} new of {len(all_tracks)} "
                f"total, using {mode} mode"
            )

            if mode == "playlist":
                new_track_ids = {t.id for t in new_tracks}
                synced_count = await self._record_playlist_mode(
                    playlist.playlist_id,
                    all_tracks,
                    new_track_ids,
                    browser,
                    recorder,
                )
            else:
                synced_count = 0
                for track in new_tracks:
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
        output_path = self.spotify_music_dir / f"{track.id}.mp3"

        logger.info(f"Recording: {track.name} by {track.artist_string}")

        await browser.play_track(track.id)
        await asyncio.sleep(2)

        recorder.start_recording(output_path)
        await asyncio.sleep(track.duration_seconds + 2)
        recorder.stop_recording()

        await browser.pause()

        tag_mp3(output_path, track)
        # Note: playlist_id will be added by _update_playlist_membership
        self.spotify_library.add_track(
            track.id, f"{track.id}.mp3", track.name, track.artist_string, ""
        )

        logger.info(f"Completed: {track.name}")

    async def _record_playlist_mode(
        self,
        playlist_id: str,
        all_tracks: list[Track],
        new_track_ids: set[str],
        browser: SpotifyBrowser,
        recorder: AudioRecorder,
    ) -> int:
        """Record tracks by playing the playlist. Returns count of tracks recorded."""
        track_map = {t.id: t for t in all_tracks}
        recorded_count = 0

        logger.info(
            f"Starting playlist mode for {len(all_tracks)} tracks "
            f"({len(new_track_ids)} new)"
        )

        # Start playing the playlist
        await browser.play_playlist(playlist_id)
        await asyncio.sleep(2)

        current_track_id = browser.get_current_track_id()
        tracks_seen: set[str] = set()

        while current_track_id and len(tracks_seen) < len(all_tracks):
            tracks_seen.add(current_track_id)
            track = track_map.get(current_track_id)

            if not track:
                logger.warning(f"Unknown track playing: {current_track_id}")
            elif current_track_id in new_track_ids:
                # Record this track
                logger.info(f"Recording: {track.name} by {track.artist_string}")
                try:
                    await self._record_current_track(track, browser, recorder)
                    recorded_count += 1
                except Exception as e:
                    logger.error(f"Failed to record {track.name}: {e}")
            else:
                # Let existing track play through
                logger.debug(f"Skipping (already have): {track.name}")

            # Wait for next track
            timeout = (track.duration_seconds + 30) if track else 300
            next_track_id = await browser.wait_for_track_change(
                current_track_id,
                timeout_seconds=timeout
            )

            if next_track_id is None:
                logger.info("Playlist finished or timed out")
                break

            current_track_id = next_track_id

        return recorded_count

    async def _record_current_track(
        self,
        track: Track,
        browser: SpotifyBrowser,
        recorder: AudioRecorder,
    ) -> None:
        """Record the currently playing track."""
        output_path = self.spotify_music_dir / f"{track.id}.mp3"

        recorder.start_recording(output_path)
        await asyncio.sleep(track.duration_seconds + 2)
        recorder.stop_recording()

        tag_mp3(output_path, track)
        self.spotify_library.add_track(
            track.id, f"{track.id}.mp3", track.name, track.artist_string, ""
        )

        logger.info(f"Completed: {track.name}")
