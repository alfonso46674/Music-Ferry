# music_ferry/tagger.py
from pathlib import Path

import requests
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, ID3NoHeaderError

from music_ferry.spotify_api import Track


def tag_mp3(mp3_path: Path, track: Track) -> None:
    try:
        audio = MP3(mp3_path)
    except ID3NoHeaderError:
        audio = MP3(mp3_path)
        audio.add_tags()

    if audio.tags is None:
        audio.add_tags()

    audio.tags["TIT2"] = TIT2(encoding=3, text=track.name)
    audio.tags["TPE1"] = TPE1(encoding=3, text=track.artist_string)
    audio.tags["TALB"] = TALB(encoding=3, text=track.album)

    if track.album_art_url:
        try:
            response = requests.get(track.album_art_url, timeout=10)
            if response.ok:
                mime_type = response.headers.get("Content-Type", "image/jpeg")
                audio.tags["APIC"] = APIC(
                    encoding=3,
                    mime=mime_type,
                    type=3,  # Cover (front)
                    desc="Cover",
                    data=response.content,
                )
        except requests.RequestException:
            pass  # Skip album art if download fails

    audio.save()
