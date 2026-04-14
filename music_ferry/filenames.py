import re
from typing import Protocol

DEFAULT_FILENAME_MAX_CHARS = 100

_FILENAME_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f%]+')
_WHITESPACE = re.compile(r"\s+")


class TrackFilenameData(Protocol):
    id: str
    name: str

    @property
    def artist_string(self) -> str: ...


def sanitize_filename_stem(value: str) -> str:
    sanitized = _FILENAME_UNSAFE_CHARS.sub(" ", value)
    sanitized = _WHITESPACE.sub(" ", sanitized)
    return sanitized.strip(" .")


def build_track_filename(
    track: TrackFilenameData,
    *,
    max_chars: int = DEFAULT_FILENAME_MAX_CHARS,
    extension: str = "mp3",
) -> str:
    suffix = f".{extension.lstrip('.')}"
    if max_chars <= len(suffix):
        raise ValueError("max_chars must leave room for a filename stem and extension")

    artist = sanitize_filename_stem(track.artist_string)
    title = sanitize_filename_stem(track.name)

    if artist and title:
        stem = f"{artist} - {title}"
    else:
        stem = title or artist or sanitize_filename_stem(track.id) or "track"

    max_stem_chars = max_chars - len(suffix)
    stem = stem[:max_stem_chars].rstrip(" .-_")
    if not stem:
        stem = "track"[:max_stem_chars]

    return f"{stem}{suffix}"
