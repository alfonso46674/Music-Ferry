# music_ferry/youtube/downloader.py
import logging
import random
import time
from pathlib import Path
from urllib.error import HTTPError

import yt_dlp
from yt_dlp.utils import DownloadError

from music_ferry.spotify_api import Track

logger = logging.getLogger(__name__)


class YouTubeDownloader:
    def __init__(
        self,
        output_dir: Path,
        bitrate: int = 192,
        max_retries: int = 1,
        retry_delay_seconds: float = 5.0,
    ):
        self.output_dir = output_dir
        self.bitrate = bitrate
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_playlist_tracks(self, playlist_url: str, playlist_name: str) -> list[Track]:
        """Fetch playlist metadata without downloading.

        Returns list of Track objects with source="youtube".
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)

        tracks = []
        for entry in info.get("entries", []):
            if entry is None:
                continue

            track = Track(
                id=entry["id"],
                name=entry.get("title", "Unknown"),
                artists=[entry.get("channel", "Unknown")],
                album=playlist_name,
                duration_ms=int(entry.get("duration", 0) * 1000),
                album_art_url=entry.get("thumbnail"),
                source="youtube",
            )
            tracks.append(track)

        return tracks

    def _progress_hook(self, d: dict) -> None:
        """Log download progress."""
        if d["status"] == "downloading":
            percent = d.get("_percent_str", "?%").strip()
            speed = d.get("_speed_str", "?").strip()
            eta = d.get("_eta_str", "?").strip()
            logger.info(f"  Progress: {percent} at {speed}, ETA: {eta}")
        elif d["status"] == "finished":
            logger.info("  Download complete, converting to MP3...")

    def _is_retryable_error(self, error: Exception) -> bool:
        if isinstance(error, DownloadError):
            original = error.__cause__
            if isinstance(original, HTTPError):
                if original.code in (403, 429) or original.code >= 500:
                    return True

        message = str(error).lower()
        retry_markers = [
            "http error 403",
            "http error 429",
            "http error 5",
            "temporarily unavailable",
            "timed out",
        ]
        return any(marker in message for marker in retry_markers)

    def download_track(self, track: Track) -> Path:
        """Download a single track as MP3.

        Returns path to the downloaded file.
        """
        output_path = self.output_dir / f"{track.id}.mp3"
        output_template = str(self.output_dir / f"{track.id}.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(self.bitrate),
                },
                {
                    "key": "EmbedThumbnail",
                },
                {
                    "key": "FFmpegMetadata",
                },
            ],
            "writethumbnail": True,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._progress_hook],
        }

        video_url = f"https://www.youtube.com/watch?v={track.id}"

        attempts = max(self.max_retries + 1, 1)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                return output_path
            except Exception as e:
                last_error = e
                should_retry = attempt < attempts and self._is_retryable_error(e)
                if not should_retry:
                    raise
                backoff = self.retry_delay_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Download failed for %s (attempt %d/%d): %s. Retrying in %.1fs",
                    track.name,
                    attempt,
                    attempts,
                    e,
                    backoff,
                )
                time.sleep(backoff)

        if last_error:
            raise last_error
        return output_path

    def download_tracks(
        self,
        tracks: list[Track],
        on_progress: callable = None,
    ) -> tuple[list[Track], list[tuple[Track, Exception]]]:
        """Download multiple tracks with random delays.

        Returns list of successfully downloaded tracks and failures.
        """
        downloaded: list[Track] = []
        failed: list[tuple[Track, Exception]] = []

        for i, track in enumerate(tracks):
            try:
                logger.info(f"Downloading: {track.name} by {track.artist_string}")
                self.download_track(track)
                downloaded.append(track)

                if on_progress:
                    on_progress(i + 1, len(tracks), track)

                # Random delay between downloads (except after last)
                if i < len(tracks) - 1:
                    delay = random.uniform(5, 15)
                    logger.debug(f"Waiting {delay:.1f}s before next download")
                    time.sleep(delay)

            except Exception as e:
                logger.error(f"Failed to download {track.name}: {e}")
                failed.append((track, e))

        return downloaded, failed
