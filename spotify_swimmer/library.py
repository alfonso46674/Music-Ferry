# spotify_swimmer/library.py
from dataclasses import dataclass, field


@dataclass
class LibraryTrack:
    id: str
    filename: str
    title: str
    artist: str
    playlists: list[str] = field(default_factory=list)

    @property
    def is_orphaned(self) -> bool:
        return len(self.playlists) == 0


@dataclass
class LibraryPlaylist:
    id: str
    name: str
    last_synced: str | None = None
    track_count: int = 0


class Library:
    """Placeholder for Task 2."""
    pass
