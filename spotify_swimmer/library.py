# spotify_swimmer/library.py
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class LibraryTrack:
    id: str
    filename: str
    title: str
    artist: str
    playlists: list[str] = field(default_factory=list)
    size_bytes: int | None = None

    @property
    def is_orphaned(self) -> bool:
        return len(self.playlists) == 0


@dataclass
class LibraryPlaylist:
    id: str
    name: str
    last_synced: str | None = None
    track_count: int = 0
    track_order: list[str] = field(default_factory=list)


class Library:
    VERSION = 1

    def __init__(self, db_path: Path, migrate_from: Path | None = None):
        self.db_path = db_path
        self._tracks: dict[str, LibraryTrack] = {}
        self._playlists: dict[str, LibraryPlaylist] = {}

        if migrate_from and migrate_from.exists() and not db_path.exists():
            self._migrate_old_format(migrate_from)
        else:
            self._load()

    def _migrate_old_format(self, old_path: Path) -> None:
        """Migrate from old tracks.json format to new library.json format."""
        with open(old_path) as f:
            old_data = json.load(f)

        # Old format: {"track_id": "filename.mp3"}
        for track_id, filename in old_data.items():
            self._tracks[track_id] = LibraryTrack(
                id=track_id,
                filename=filename,
                title="Unknown",
                artist="Unknown",
                playlists=[],  # Will be populated on next sync
            )

        self.save()

    def _load(self) -> None:
        if not self.db_path.exists():
            return

        with open(self.db_path) as f:
            data = json.load(f)

        for track_id, track_data in data.get("tracks", {}).items():
            self._tracks[track_id] = LibraryTrack(
                id=track_id,
                filename=track_data["filename"],
                title=track_data["title"],
                artist=track_data["artist"],
                playlists=track_data.get("playlists", []),
                size_bytes=track_data.get("size_bytes"),
            )

        for playlist_id, playlist_data in data.get("playlists", {}).items():
            self._playlists[playlist_id] = LibraryPlaylist(
                id=playlist_id,
                name=playlist_data["name"],
                last_synced=playlist_data.get("last_synced"),
                track_count=playlist_data.get("track_count", 0),
                track_order=playlist_data.get("track_order", []),
            )

    def save(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self.VERSION,
            "tracks": {
                track_id: {
                    "filename": track.filename,
                    "title": track.title,
                    "artist": track.artist,
                    "playlists": track.playlists,
                    "size_bytes": track.size_bytes,
                }
                for track_id, track in self._tracks.items()
            },
            "playlists": {
                playlist_id: {
                    "name": playlist.name,
                    "last_synced": playlist.last_synced,
                    "track_count": playlist.track_count,
                    "track_order": playlist.track_order,
                }
                for playlist_id, playlist in self._playlists.items()
            },
        }

        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2)

    def get_track(self, track_id: str) -> LibraryTrack | None:
        return self._tracks.get(track_id)

    def get_all_tracks(self) -> list[LibraryTrack]:
        return list(self._tracks.values())

    def get_all_playlists(self) -> list[LibraryPlaylist]:
        return list(self._playlists.values())

    def is_downloaded(self, track_id: str) -> bool:
        return track_id in self._tracks

    def add_track(
        self,
        track_id: str,
        filename: str,
        title: str,
        artist: str,
        playlist_id: str,
        size_bytes: int | None = None,
    ) -> None:
        if track_id in self._tracks:
            self.add_track_to_playlist(track_id, playlist_id)
            if size_bytes is not None:
                self._tracks[track_id].size_bytes = size_bytes
                self.save()
        else:
            self._tracks[track_id] = LibraryTrack(
                id=track_id,
                filename=filename,
                title=title,
                artist=artist,
                playlists=[playlist_id],
                size_bytes=size_bytes,
            )
            self.save()

    def add_track_to_playlist(self, track_id: str, playlist_id: str) -> None:
        track = self._tracks.get(track_id)
        if track and playlist_id not in track.playlists:
            track.playlists.append(playlist_id)
            self.save()

    def remove_track_from_playlist(self, track_id: str, playlist_id: str) -> None:
        track = self._tracks.get(track_id)
        if track and playlist_id in track.playlists:
            track.playlists.remove(playlist_id)
            self.save()

    def delete_track(self, track_id: str) -> None:
        if track_id in self._tracks:
            del self._tracks[track_id]
            self.save()

    def get_playlist(self, playlist_id: str) -> LibraryPlaylist | None:
        return self._playlists.get(playlist_id)

    def update_playlist(
        self,
        playlist_id: str,
        name: str,
        track_count: int = 0,
        track_order: list[str] | None = None,
    ) -> None:
        existing = self._playlists.get(playlist_id)
        self._playlists[playlist_id] = LibraryPlaylist(
            id=playlist_id,
            name=name,
            last_synced=datetime.now().isoformat(),
            track_count=track_count,
            track_order=track_order or (existing.track_order if existing else []),
        )
        self.save()

    def get_tracks_for_playlist(self, playlist_id: str) -> list[LibraryTrack]:
        return [
            track for track in self._tracks.values()
            if playlist_id in track.playlists
        ]

    def get_orphaned_tracks(self) -> list[LibraryTrack]:
        return [track for track in self._tracks.values() if track.is_orphaned]
