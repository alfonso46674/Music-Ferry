# music_ferry/youtube/downloader.py
import logging
import random
import time
from pathlib import Path

import yt_dlp

from music_ferry.spotify_api import Track

logger = logging.getLogger(__name__)


class YouTubeDownloader:
    def __init__(self, output_dir: Path, bitrate: int = 192):
        self.output_dir = output_dir
        self.bitrate = bitrate
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

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        return output_path

    def download_tracks(
        self,
        tracks: list[Track],
        on_progress: callable = None,
    ) -> list[Track]:
        """Download multiple tracks with random delays.

        Returns list of successfully downloaded tracks.
        """
        downloaded: list[Track] = []

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

        return downloaded
