# YouTube Support Design

## Overview

Add YouTube playlist support to Music Ferry, allowing users to download YouTube playlists as MP3s alongside Spotify playlists. Both sources sync to the same headphones with tracks mixed in a flat folder.

## Key Decisions

| Aspect | Decision |
|--------|----------|
| YouTube download method | yt-dlp (direct download, no browser recording) |
| Library separation | Separate folders: `spotify/` and `youtube/` |
| Track identification | YouTube video ID (11 chars), mirrors Spotify pattern |
| Metadata tagging | Channel → Artist, Playlist → Album, Thumbnail → Cover |
| Config structure | Symmetric: `spotify.playlists` and `youtube.playlists` |
| CLI flags | `--spotify` / `--youtube` for both `sync` and `transfer` |
| Download pacing | Sequential with 5-15 second random delays |
| Audio/behavior settings | Shared across both sources |
| Headphones transfer | Flat folder, all tracks mixed together |

## Architecture

### Directory Structure

```
~/.music-ferry/
├── config.yaml
├── cookies/                    # Spotify browser cookies
├── spotify/
│   ├── library.json
│   └── music/*.mp3
└── youtube/
    ├── library.json
    └── music/*.mp3
```

### Module Structure

```
music_ferry/
├── youtube/                    # NEW: YouTube-specific modules
│   ├── __init__.py
│   └── downloader.py           # yt-dlp wrapper
├── library.py                  # Unchanged (reused per-source)
├── tagger.py                   # Shared (works for both)
├── transfer.py                 # Updated (merges both sources)
├── orchestrator.py             # Updated (coordinates both sources)
├── config.py                   # Updated (adds youtube config)
├── cli.py                      # Updated (adds --spotify/--youtube flags)
├── notify.py                   # Unchanged
├── spotify_api.py              # Updated (add source field to Track)
├── browser.py                  # Unchanged (Spotify only)
└── recorder.py                 # Unchanged (Spotify only)
```

## Configuration

### Updated config.yaml

```yaml
spotify:
  enabled: true                    # NEW: defaults to true if omitted
  client_id: "YOUR_CLIENT_ID"
  client_secret: "YOUR_CLIENT_SECRET"
  username: "YOUR_USERNAME"
  playlists:                       # MOVED: now under spotify section
    - name: "Discover Weekly"
      url: "https://open.spotify.com/playlist/..."
    - name: "Workout Mix"
      url: "https://open.spotify.com/playlist/..."

youtube:                           # NEW SECTION
  enabled: true                    # defaults to true if omitted
  playlists:
    - name: "Coding Music"
      url: "https://www.youtube.com/playlist?list=PLxxxxxxx"
    - name: "Workout Beats"
      url: "https://www.youtube.com/playlist?list=PLyyyyyyy"

audio:
  bitrate: 192                     # applies to both sources
  format: "mp3"

paths:
  music_dir: "~/.music-ferry"  # base dir, /spotify and /youtube added
  headphones_mount: "/media/user/HEADPHONES"
  headphones_music_folder: "Music"

notifications:
  ntfy_topic: "your-secret-topic"
  ntfy_server: "https://ntfy.sh"
  notify_on_success: false
  notify_on_failure: true

behavior:
  skip_existing: true              # applies to both sources
  trim_silence: true               # Spotify only (ignored for YouTube)
```

### Backward Compatibility

- If `spotify.enabled` is missing → defaults to `true`
- If `youtube` section is missing → YouTube disabled
- Existing configs need migration: move `playlists` under `spotify.playlists`

## CLI Interface

### Sync Command

```bash
# Sync both sources (default behavior)
music-ferry sync

# Sync only Spotify
music-ferry sync --spotify

# Sync only YouTube
music-ferry sync --youtube

# Explicit both (same as no flags)
music-ferry sync --spotify --youtube

# Combined with existing flags
music-ferry -v sync --youtube
music-ferry -c /path/to/config.yaml sync --spotify
```

### Transfer Command

```bash
# Transfer both sources (default)
music-ferry transfer

# Transfer Spotify tracks only
music-ferry transfer --spotify

# Transfer YouTube tracks only
music-ferry transfer --youtube

# Explicit both
music-ferry transfer --spotify --youtube
```

### Flag Behavior

**Sync:**
- No flags → sync all enabled sources from config
- `--spotify` only → sync Spotify regardless of config `enabled`
- `--youtube` only → sync YouTube regardless of config `enabled`
- Both flags → sync both regardless of config

**Transfer:**
- No flags → merge both libraries, transfer all to headphones
- `--spotify` → only show/transfer Spotify tracks
- `--youtube` → only show/transfer YouTube tracks
- Both flags → same as no flags (all tracks)

## YouTube Downloader Module

### YouTubeDownloader Class

```python
class YouTubeDownloader:
    def __init__(self, output_dir: Path, bitrate: int = 192):
        self.output_dir = output_dir
        self.bitrate = bitrate

    def get_playlist_tracks(self, playlist_url: str) -> list[Track]:
        """Fetch playlist metadata without downloading.

        Uses yt-dlp to extract:
        - Video IDs
        - Video titles
        - Channel names
        - Durations
        - Thumbnail URLs

        Returns list of Track objects with source="youtube".
        """

    def download_track(self, video_id: str, playlist_name: str) -> Path:
        """Download single video as MP3, return path to file.

        Uses yt-dlp with:
        - -x (extract audio)
        - --audio-format mp3
        - --audio-quality {bitrate}
        - --embed-thumbnail

        Tags MP3 with:
        - Title: video title
        - Artist: channel name
        - Album: playlist name
        - Cover: video thumbnail
        """

    def download_playlist_tracks(
        self,
        tracks: list[Track],
        playlist_name: str,
        on_progress: Callable = None
    ) -> int:
        """Download multiple tracks with delays.

        - Sequential downloads (one at a time)
        - Random 5-15 second delay between downloads
        - Returns count of successfully downloaded tracks
        """
```

### Track Dataclass Update

```python
@dataclass
class Track:
    id: str              # Spotify track ID or YouTube video ID
    name: str            # Song title or video title
    artists: list[str]   # Artist names or [channel name]
    album: str           # Album name or playlist name
    duration_ms: int
    album_art_url: str | None
    source: str = "spotify"    # NEW: "spotify" or "youtube"

    @property
    def artist_string(self) -> str:
        return ", ".join(self.artists)
```

## Orchestrator Changes

### Updated Sync Flow

```python
class Orchestrator:
    def __init__(self, config: Config):
        self.config = config

        # Initialize both source handlers
        spotify_base = config.paths.music_dir / "spotify"
        youtube_base = config.paths.music_dir / "youtube"

        self.spotify_library = Library(
            spotify_base / "library.json",
            migrate_from=config.paths.music_dir.parent / "library.json"  # old location
        )
        self.youtube_library = Library(youtube_base / "library.json")

    async def run(
        self,
        sync_spotify: bool = True,
        sync_youtube: bool = True
    ) -> SyncResult:
        """Run sync for selected sources."""

        results = []

        if sync_spotify and self.config.spotify.enabled:
            spotify_result = await self._sync_spotify()
            results.append(("spotify", spotify_result))

        if sync_youtube and self.config.youtube.enabled:
            youtube_result = await self._sync_youtube()
            results.append(("youtube", youtube_result))

        # Combine results, send notification
        return self._combine_results(results)

    async def _sync_spotify(self) -> list[PlaylistResult]:
        """Existing Spotify sync logic (browser recording).

        Uses: SpotifyAPI, SpotifyBrowser, AudioRecorder
        Features: Playback mode selection, playlist membership, orphan cleanup
        """

    async def _sync_youtube(self) -> list[PlaylistResult]:
        """New YouTube sync logic (direct download).

        Uses: YouTubeDownloader
        Pattern: Fetch metadata → filter new → download → tag → cleanup orphans

        Key differences from Spotify:
        - No browser or recorder needed
        - Direct download via yt-dlp
        - Faster (no real-time recording)
        - Sequential with delays to avoid rate limiting
        """
```

## Transfer Changes

### Updated InteractiveTransfer

```python
class InteractiveTransfer:
    def __init__(
        self,
        config,
        sources: list[str] = None,  # None means both
        spotify_library: Library = None,
        youtube_library: Library = None
    ):
        self.config = config
        self.sources = sources or ["spotify", "youtube"]

        # Load libraries for selected sources
        self.libraries = {}
        if "spotify" in self.sources:
            self.libraries["spotify"] = spotify_library or Library(...)
        if "youtube" in self.sources:
            self.libraries["youtube"] = youtube_library or Library(...)

    def _get_all_local_files(self) -> dict[str, Path]:
        """Get all MP3s from selected sources.

        Returns {filename: full_path} mapping.
        Files from different sources may have same name pattern but different paths.
        """
        files = {}
        if "spotify" in self.sources:
            spotify_music = self.config.paths.music_dir / "spotify" / "music"
            for f in spotify_music.glob("*.mp3"):
                files[f.name] = f
        if "youtube" in self.sources:
            youtube_music = self.config.paths.music_dir / "youtube" / "music"
            for f in youtube_music.glob("*.mp3"):
                files[f.name] = f
        return files

    def compute_status(self) -> TransferStatus:
        """Combined status across selected sources.

        Merges tracks from all selected libraries.
        PlaylistStatus includes source info for display.
        """

    def sync_changes(self) -> tuple[int, int]:
        """Copy new files from all sources, remove orphans.

        Copies from:
        - spotify/music/*.mp3
        - youtube/music/*.mp3

        To flat folder:
        - /media/user/HEADPHONES/Music/*.mp3
        """
```

### Headphones Result

All tracks mixed in flat folder:

```
/media/user/HEADPHONES/Music/
├── 4iV5W9uYEdYUVa79Axb7Rh.mp3    # Spotify track
├── dQw4w9WgXcQ.mp3                # YouTube track
├── 7ouMYWGrCkc.mp3                # YouTube track
└── 2TpxZ7JUBn1rvPFD4W.mp3        # Spotify track
```

## Dependencies

### New Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing deps
    "yt-dlp>=2024.0.0",
]
```

## Migration

### Config Migration

Existing configs have `playlists` at root level. New configs need it under `spotify.playlists`.

**Option 1: Manual migration** - Document the change, users update their configs.

**Option 2: Auto-migration** - Detect old format and move playlists automatically:

```python
def load_config(config_path: Path) -> Config:
    data = yaml.safe_load(...)

    # Auto-migrate: move root playlists to spotify.playlists
    if "playlists" in data and "playlists" not in data.get("spotify", {}):
        data.setdefault("spotify", {})["playlists"] = data.pop("playlists")

    # ... rest of loading
```

Recommend Option 2 for seamless upgrade.

### Library Migration

Existing library at `~/.music-ferry/library.json` needs to move to `~/.music-ferry/spotify/library.json`.

Handle in Orchestrator `__init__`:
```python
old_library = music_dir.parent / "library.json"
new_library = music_dir / "spotify" / "library.json"
if old_library.exists() and not new_library.exists():
    # Migrate old library to new location
```

## Files to Create

- `music_ferry/youtube/__init__.py`
- `music_ferry/youtube/downloader.py`
- `tests/test_youtube_downloader.py`

## Files to Modify

- `music_ferry/config.py` - Add YouTube config, move playlists under spotify, add enabled fields
- `music_ferry/cli.py` - Add `--spotify`/`--youtube` flags to sync and transfer
- `music_ferry/orchestrator.py` - Add YouTube sync path, handle both libraries
- `music_ferry/transfer.py` - Merge multiple sources for transfer
- `music_ferry/spotify_api.py` - Add `source` field to Track dataclass
- `pyproject.toml` - Add yt-dlp dependency
- `README.md` - Document YouTube support
- `scripts/install-systemd.sh` - Update sample config

## Testing Strategy

1. **Unit tests for YouTubeDownloader** - Mock yt-dlp calls
2. **Config parsing tests** - New YouTube section, migration
3. **CLI tests** - New flags for sync and transfer
4. **Transfer tests** - Multi-source merging
5. **Integration tests** - Full workflow with both sources
