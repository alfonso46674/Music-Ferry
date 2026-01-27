# music_ferry/config.py
from dataclasses import dataclass, field
from pathlib import Path
import re

import yaml


@dataclass
class PlaylistConfig:
    name: str
    url: str
    max_gb: float | None = None

    @property
    def playlist_id(self) -> str:
        # Try Spotify URL format: playlist/[id]
        spotify_match = re.search(r"playlist/([a-zA-Z0-9]+)", self.url)
        if spotify_match:
            return spotify_match.group(1)

        # Try YouTube URL format: ?list=[id] or &list=[id]
        youtube_match = re.search(r"[?&]list=([a-zA-Z0-9_-]+)", self.url)
        if youtube_match:
            return youtube_match.group(1)

        raise ValueError(f"Invalid playlist URL: {self.url}")


@dataclass
class SpotifyConfig:
    client_id: str
    client_secret: str
    username: str
    enabled: bool = True
    playlists: list[PlaylistConfig] = field(default_factory=list)


@dataclass
class YouTubeConfig:
    enabled: bool = False
    playlists: list[PlaylistConfig] = field(default_factory=list)
    retry_count: int = 1
    retry_delay_seconds: float = 5.0


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
    trim_silence: bool = True


@dataclass
class TransferConfig:
    reserve_free_gb: float = 0.0


@dataclass
class Config:
    spotify: SpotifyConfig
    youtube: YouTubeConfig
    audio: AudioConfig
    paths: PathsConfig
    notifications: NotificationsConfig
    behavior: BehaviorConfig
    transfer: TransferConfig


def load_config(config_path: Path) -> Config:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    # Validate required spotify fields (only if enabled)
    spotify_data = data.get("spotify", {})
    spotify_enabled = spotify_data.get("enabled", True)
    if spotify_enabled:
        for required in ["client_id", "client_secret", "username"]:
            if required not in spotify_data:
                raise ValueError(f"Missing required spotify field: {required}")

    # Parse Spotify playlists - check both spotify.playlists and root-level playlists (backward compat)
    spotify_playlists_data = spotify_data.get("playlists", [])
    root_playlists_data = data.get("playlists", [])

    # Migrate root-level playlists to spotify.playlists for backward compatibility
    if root_playlists_data and not spotify_playlists_data:
        spotify_playlists_data = root_playlists_data

    spotify_playlists = [
        PlaylistConfig(
            name=p["name"],
            url=p["url"],
            max_gb=p.get("max_gb"),
        )
        for p in spotify_playlists_data
    ]

    spotify = SpotifyConfig(
        client_id=spotify_data.get("client_id", ""),
        client_secret=spotify_data.get("client_secret", ""),
        username=spotify_data.get("username", ""),
        enabled=spotify_enabled,
        playlists=spotify_playlists,
    )

    # Parse YouTube config
    youtube_data = data.get("youtube", {})
    youtube_playlists = [
        PlaylistConfig(
            name=p["name"],
            url=p["url"],
            max_gb=p.get("max_gb"),
        )
        for p in youtube_data.get("playlists", [])
    ]
    youtube = YouTubeConfig(
        enabled=youtube_data.get("enabled", False),
        playlists=youtube_playlists,
        retry_count=youtube_data.get("retry_count", 1),
        retry_delay_seconds=youtube_data.get("retry_delay_seconds", 5.0),
    )

    audio_data = data.get("audio", {})
    audio = AudioConfig(
        bitrate=audio_data.get("bitrate", 192),
        format=audio_data.get("format", "mp3"),
    )

    paths_data = data.get("paths", {})
    paths = PathsConfig(
        music_dir=paths_data.get("music_dir", "~/.music-ferry"),
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
        trim_silence=behavior_data.get("trim_silence", True),
    )

    transfer_data = data.get("transfer", {})
    transfer = TransferConfig(
        reserve_free_gb=transfer_data.get("reserve_free_gb", 0.0),
    )

    return Config(
        spotify=spotify,
        youtube=youtube,
        audio=audio,
        paths=paths,
        notifications=notifications,
        behavior=behavior,
        transfer=transfer,
    )
