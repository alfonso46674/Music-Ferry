# music_ferry/tagger.py
import logging
from pathlib import Path
from typing import Any, cast

import requests  # type: ignore[import-untyped]
from mutagen.id3 import (  # type: ignore[attr-defined]
    APIC,
    TALB,
    TIT2,
    TPE1,
    ID3NoHeaderError,
)
from mutagen.mp3 import MP3

from music_ferry.spotify_api import Track

logger = logging.getLogger(__name__)


def tag_mp3(mp3_path: Path, track: Track) -> None:
    try:
        audio = cast(Any, MP3(mp3_path))
    except ID3NoHeaderError:
        audio = cast(Any, MP3(mp3_path))
        audio.add_tags()

    if audio.tags is None:
        audio.add_tags()

    audio.tags["TIT2"] = cast(Any, TIT2)(encoding=3, text=track.name)
    audio.tags["TPE1"] = cast(Any, TPE1)(encoding=3, text=track.artist_string)
    audio.tags["TALB"] = cast(Any, TALB)(encoding=3, text=track.album)

    if track.album_art_url:
        try:
            response = requests.get(track.album_art_url, timeout=10)
            if response.ok:
                mime_type = response.headers.get("Content-Type", "image/jpeg")
                audio.tags["APIC"] = cast(Any, APIC)(
                    encoding=3,
                    mime=mime_type,
                    type=3,  # Cover (front)
                    desc="Cover",
                    data=response.content,
                )
        except requests.RequestException as exc:
            logger.warning("Failed to download album art for %s: %s", track.id, exc)

    audio.save()
