# music_ferry/spotify_api.py
from dataclasses import dataclass

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


@dataclass
class Track:
    id: str
    name: str
    artists: list[str]
    album: str
    duration_ms: int
    album_art_url: str | None
    source: str = "spotify"

    @property
    def duration_seconds(self) -> int:
        return self.duration_ms // 1000

    @property
    def artist_string(self) -> str:
        return ", ".join(self.artists)


class SpotifyAPI:
    def __init__(self, client_id: str, client_secret: str):
        auth_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)

    def get_playlist_tracks(self, playlist_id: str) -> list[Track]:
        tracks: list[Track] = []
        results = self.sp.playlist_items(playlist_id)

        while results:
            for item in results["items"]:
                track_data = item.get("track")
                if track_data is None:
                    continue

                images = track_data["album"].get("images", [])
                album_art_url = images[0]["url"] if images else None

                track = Track(
                    id=track_data["id"],
                    name=track_data["name"],
                    artists=[a["name"] for a in track_data["artists"]],
                    album=track_data["album"]["name"],
                    duration_ms=track_data["duration_ms"],
                    album_art_url=album_art_url,
                )
                tracks.append(track)

            if results["next"]:
                results = self.sp.next(results)
            else:
                break

        return tracks
