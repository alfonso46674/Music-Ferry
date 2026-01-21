# spotify_swimmer/config.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import re

import yaml


@dataclass
class SpotifyConfig:
    client_id: str
    client_secret: str
    username: str


@dataclass
class PlaylistConfig:
    name: str
    url: str

    @property
    def playlist_id(self) -> str:
        match = re.search(r"playlist/([a-zA-Z0-9]+)", self.url)
        if not match:
            raise ValueError(f"Invalid playlist URL: {self.url}")
        return match.group(1)


@dataclass
class AudioConfig:
    bitrate: int = 192
    format: str = "mp3"


@dataclass
class PathsConfig:
    music_dir: Path
    headphones_mount: Path
    headphones_music_folder: str = "Music"

    def __post_init__(self):
        if isinstance(self.music_dir, str):
            self.music_dir = Path(self.music_dir).expanduser()
        if isinstance(self.headphones_mount, str):
            self.headphones_mount = Path(self.headphones_mount)


@dataclass
class NotificationsConfig:
    ntfy_topic: str
    ntfy_server: str = "https://ntfy.sh"
    notify_on_success: bool = False
    notify_on_failure: bool = True


@dataclass
class BehaviorConfig:
    skip_existing: bool = True
    auto_transfer: bool = True
    trim_silence: bool = True


@dataclass
class Config:
    spotify: SpotifyConfig
    playlists: list[PlaylistConfig]
    audio: AudioConfig
    paths: PathsConfig
    notifications: NotificationsConfig
    behavior: BehaviorConfig


def load_config(config_path: Path) -> Config:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    # Validate required spotify fields
    spotify_data = data.get("spotify", {})
    for required in ["client_id", "client_secret", "username"]:
        if required not in spotify_data:
            raise ValueError(f"Missing required spotify field: {required}")

    spotify = SpotifyConfig(
        client_id=spotify_data["client_id"],
        client_secret=spotify_data["client_secret"],
        username=spotify_data["username"],
    )

    playlists = [
        PlaylistConfig(name=p["name"], url=p["url"])
        for p in data.get("playlists", [])
    ]

    audio_data = data.get("audio", {})
    audio = AudioConfig(
        bitrate=audio_data.get("bitrate", 192),
        format=audio_data.get("format", "mp3"),
    )

    paths_data = data.get("paths", {})
    paths = PathsConfig(
        music_dir=paths_data.get("music_dir", "~/.spotify-swimmer/music"),
        headphones_mount=paths_data.get("headphones_mount", "/media/user/HEADPHONES"),
        headphones_music_folder=paths_data.get("headphones_music_folder", "Music"),
    )

    notif_data = data.get("notifications", {})
    notifications = NotificationsConfig(
        ntfy_topic=notif_data.get("ntfy_topic", ""),
        ntfy_server=notif_data.get("ntfy_server", "https://ntfy.sh"),
        notify_on_success=notif_data.get("notify_on_success", False),
        notify_on_failure=notif_data.get("notify_on_failure", True),
    )

    behavior_data = data.get("behavior", {})
    behavior = BehaviorConfig(
        skip_existing=behavior_data.get("skip_existing", True),
        auto_transfer=behavior_data.get("auto_transfer", True),
        trim_silence=behavior_data.get("trim_silence", True),
    )

    return Config(
        spotify=spotify,
        playlists=playlists,
        audio=audio,
        paths=paths,
        notifications=notifications,
        behavior=behavior,
    )
