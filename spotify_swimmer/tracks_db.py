# spotify_swimmer/tracks_db.py
import json
from pathlib import Path


class TracksDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._tracks: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if self.db_path.exists():
            with open(self.db_path) as f:
                self._tracks = json.load(f)

    def save(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, "w") as f:
            json.dump(self._tracks, f, indent=2)

    def is_downloaded(self, track_id: str) -> bool:
        return track_id in self._tracks

    def add_track(self, track_id: str, filename: str) -> None:
        self._tracks[track_id] = filename
        self.save()

    def get_filename(self, track_id: str) -> str | None:
        return self._tracks.get(track_id)

    def remove_track(self, track_id: str) -> None:
        if track_id in self._tracks:
            del self._tracks[track_id]
            self.save()

    def list_tracks(self) -> dict[str, str]:
        return dict(self._tracks)
