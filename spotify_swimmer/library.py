# spotify_swimmer/library.py
import json
from dataclasses import dataclass, field
from pathlib import Path


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
    VERSION = 1

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._tracks: dict[str, LibraryTrack] = {}
        self._playlists: dict[str, LibraryPlaylist] = {}
        self._load()

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
            )

        for playlist_id, playlist_data in data.get("playlists", {}).items():
            self._playlists[playlist_id] = LibraryPlaylist(
                id=playlist_id,
                name=playlist_data["name"],
                last_synced=playlist_data.get("last_synced"),
                track_count=playlist_data.get("track_count", 0),
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
                }
                for track_id, track in self._tracks.items()
            },
            "playlists": {
                playlist_id: {
                    "name": playlist.name,
                    "last_synced": playlist.last_synced,
                    "track_count": playlist.track_count,
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
    ) -> None:
        if track_id in self._tracks:
            self.add_track_to_playlist(track_id, playlist_id)
        else:
            self._tracks[track_id] = LibraryTrack(
                id=track_id,
                filename=filename,
                title=title,
                artist=artist,
                playlists=[playlist_id],
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
