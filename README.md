# Music Ferry

[![CI](https://github.com/alfonso46674/music-ferry/actions/workflows/ci.yml/badge.svg)](https://github.com/alfonso46674/music-ferry/actions/workflows/ci.yml)

Music Ferry - ferrying music to your headphones. Download Spotify and YouTube playlists to MP3 files for offline listening.

## How It Works

1. **Checks for new tracks** - compares playlist metadata against local library
2. **Skips fully-synced playlists** - only starts browser if there are new tracks
3. **Selects playback mode** - uses playlist mode when >=70% of tracks are new (looks more natural)
4. **Plays tracks** via browser automation (Spotify Web Player)
5. **Records the audio** from a virtual PipeWire sink using FFmpeg
6. **Downloads YouTube** playlists directly via yt-dlp (no browser needed)
7. **Tags MP3 files** with ID3 metadata (title, artist, album, cover art)
8. **Tracks playlist membership** - knows which tracks belong to which playlists
9. **Cleans up orphans** - removes tracks no longer in any playlist
10. **Runs automatically** on the schedule configured in the web UI (Docker deployment)
11. **Transfer on demand** - manual command to transfer to headphones
12. **Sends notifications** via Ntfy on success/failure

## Requirements

- Linux with PipeWire/PulseAudio
- Python 3.11+
- FFmpeg
- Xvfb (for headless browser)
- rsync

## Installation

### Docker Compose (recommended)

Music Ferry is now deployed as a Docker Compose stack (no systemd jobs).

```bash
# 1) Create Docker env file
cp .env.docker.example .env.docker

# 2) Edit .env.docker and set:
#    - MUSIC_FERRY_DATA (host path with config/library files)
#    - HOST_MEDIA_DIR and HOST_RUN_MEDIA_DIR if needed

# 3) Start the web container
docker compose --env-file .env.docker up -d --build
```

Open `http://localhost:4444` and configure automatic sync schedule in the web UI.

### Updating

```bash
# Pull latest code first, then rebuild/restart
docker compose --env-file .env.docker up -d --build
```

### Stop

```bash
docker compose --env-file .env.docker down
```

### Local Development (optional)

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Install Playwright browser (only needed for local Spotify sync/testing)
playwright install chromium
```

## Configuration

Edit `~/.music-ferry/config.yaml`:

```yaml
spotify:
  enabled: true
  client_id: "YOUR_SPOTIFY_CLIENT_ID"
  client_secret: "YOUR_SPOTIFY_CLIENT_SECRET"
  username: "YOUR_SPOTIFY_USERNAME"
  playlists:
    - name: "Discover Weekly"
      url: "https://open.spotify.com/playlist/37i9dQZEVXcQ9COmYvdajy"
      max_gb: 1.5
    - name: "Workout Mix"
      url: "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID"

youtube:
  enabled: false
  retry_count: 1
  retry_delay_seconds: 5.0
  cookies_file: "~/.music-ferry/cookies/youtube-cookies.txt"  # optional
  playlists:
    - name: "Coding Music"
      url: "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"
      max_gb: 2.0

audio:
  bitrate: 192  # kbps
  format: "mp3"

paths:
  music_dir: "~/.music-ferry"
  headphones_mount: "/media/yourusername/HEADPHONES"
  headphones_music_folder: "Music"

notifications:
  ntfy_topic: "your-secret-topic"
  ntfy_server: "https://ntfy.sh"
  notify_on_success: false
  notify_on_failure: true

behavior:
  skip_existing: true
  trim_silence: true

transfer:
  reserve_free_gb: 1.0
```

### Getting Spotify Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new application
3. Copy the Client ID and Client Secret to your config

### Setting Up Ntfy Notifications

1. Install the [Ntfy app](https://ntfy.sh/) on your phone
2. Subscribe to a topic (use a random string for privacy)
3. Add the topic name to your config

### YouTube Support

YouTube playlists are downloaded directly using yt-dlp - no browser automation required.

**Adding YouTube playlists:**

1. Set `youtube.enabled: true` in your config
2. Add playlists under `youtube.playlists` with name and URL
3. Run `music-ferry sync` or `music-ferry sync --youtube`

**YouTube retry options:**

- `youtube.retry_count`: how many retries per track (default: 1)
- `youtube.retry_delay_seconds`: base delay before retry in seconds (default: 5.0)

**YouTube auth option (for persistent 403 / restricted videos):**

- `youtube.cookies_file`: path to a Netscape-format YouTube cookies file exported from your browser session

**Source flags:**

- `--spotify` - sync/transfer only Spotify tracks
- `--youtube` - sync/transfer only YouTube tracks
- No flag - sync/transfer both sources (default)

**Directory structure:**

Tracks are organized by source:
```
~/.music-ferry/
├── config.yaml
├── cookies/           # Spotify login cookies
├── spotify/
│   ├── library.json   # Track database
│   └── music/         # MP3 files
└── youtube/
    ├── library.json
    └── music/
```

## Usage

### Commands

Music Ferry has three commands:

- **`sync`** - Downloads new tracks and cleans up orphaned files
- **`transfer`** - Interactive menu to transfer music to headphones
- **`serve`** - Start the web UI server with Prometheus metrics

```bash
# Sync both Spotify and YouTube (default)
music-ferry sync

# Sync only Spotify
music-ferry sync --spotify

# Sync only YouTube
music-ferry sync --youtube

# Transfer all tracks to headphones
music-ferry transfer

# Transfer to headphones (auto-select to fit size limits)
music-ferry transfer --auto

# Transfer only Spotify tracks
music-ferry transfer --spotify

# Start web UI (default: http://127.0.0.1:4444)
music-ferry serve

# Web UI on custom port
music-ferry serve --port 8080

# With verbose logging
music-ferry -v sync

# With custom config path
music-ferry -c /path/to/config.yaml sync
```

### Sync Command

The `sync` command:
1. Fetches playlist metadata from Spotify API / YouTube
2. Downloads new tracks (browser recording for Spotify, yt-dlp for YouTube)
3. Updates playlist membership tracking
4. Removes orphaned tracks (no longer in any playlist)

### Transfer Command

The `transfer` command provides an interactive menu:
1. View status (tracks to sync, orphaned files)
2. Sync changes (copy new, remove orphans from headphones)
3. Full reset (delete all, copy fresh)
4. View detailed track list by playlist

### Web UI

The `serve` command starts a web dashboard with:
- **Real-time status** - sync state, library stats
- **Trigger syncs** - start sync from the browser
- **Schedule control** - configure automatic sync time/source from the browser
- **Headphones transfer** - scan, prepare, and transfer to selected device
- **Live logs** - streaming log output via SSE
- **Prometheus metrics** - exposed at `/metrics`

```bash
# Start/rebuild the web UI container
docker compose --env-file .env.docker up -d --build
```

See [docs/web-ui.md](docs/web-ui.md) for full documentation including API reference, reverse proxy setup, and Prometheus configuration.

### First Run (Login)

The first time you run, you'll need to log into Spotify:

1. Run `music-ferry sync` manually
2. The browser will open (or check logs for any login prompts)
3. Cookies are saved for future automated runs

### Automatic Scheduling

Automatic sync is configured from the web UI:

1. Open `Schedule`.
2. Enable automatic sync.
3. Set time (HH:MM local time) and source (`youtube` / `all` / `spotify`).

Transfer is always manual (your headphones may not be connected during automated runs).

### Docker Compose Runtime Details

Use this if you need migration details beyond the quick install steps.

**1) (Optional) If migrating from an older systemd setup, disable old units:**

```bash
systemctl --user disable --now music-ferry-web.service || true
systemctl --user disable --now music-ferry.timer || true
```

**2) Create Docker env file:**

```bash
cp .env.docker.example .env.docker
# Edit .env.docker and set MUSIC_FERRY_DATA to your host data directory
```

`MUSIC_FERRY_DATA` must point to the folder that contains your `config.yaml`
(for example `~/.music-ferry`).

**3) Configure YouTube-only mode in your config.yaml:**

```yaml
spotify:
  enabled: false
youtube:
  enabled: true
paths:
  # Keep this as the real host mount path.
  # The container bind-mounts /media and /run/media with mount propagation.
  headphones_mount: "/media/YOUR_USER/HEADPHONES"
```

**4) Start the container:**

```bash
docker compose --env-file .env.docker up -d --build
```

**5) Configure automatic sync schedule in UI:**

Open the dashboard and set:
1. `Schedule` -> enable automatic sync
2. Time (HH:MM local time)
3. Source (`youtube` / `all` / `spotify`)

This replaces the old cron/systemd timer behavior while keeping idle resource usage low.

**Headphones remount/unlock workflow (host side):**

Containers can transfer files, but mounting/unlocking removable storage should be done on the host:

```bash
# Plain partition
./scripts/headphones-mount.sh --device /dev/sdb1

# Encrypted (LUKS) volume
./scripts/headphones-mount.sh --unlock-device /dev/sdb2
```

After mounting, open the web UI and use:
1. `Scan Headphones`
2. `Make Accessible` (if needed)
3. `Transfer to Selected Headphones`
4. `Prepare Safe Unplug` before unplugging

You can still trigger sync manually from the UI with `Trigger Sync`.

Unmount/lock when done:

```bash
./scripts/headphones-unmount.sh --device /dev/sdb1
# or with lock
./scripts/headphones-unmount.sh --device /dev/mapper/<name> --lock-device /dev/sdb2
```

**Optional: enable host privileged helper for UI safe-unplug (recommended):**

```bash
sudo cp systemd/music-ferry-unplug-helper.service /etc/systemd/system/
sudo tee /etc/default/music-ferry-unplug-helper >/dev/null <<'EOF'
HELPER_BIND=0.0.0.0
HELPER_PORT=17888
HELPER_TOKEN=replace-with-random-token
HELPER_CONFIG_PATH=/home/alfonso/.music-ferry/config.yaml
# Optional explicit override:
# HELPER_ALLOWED_MOUNT=/media/alfonso/681B-7309
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now music-ferry-unplug-helper.service
```

Then set in `.env.docker`:

```bash
# Use the web container's bridge gateway IP as helper host.
# Example shown for spotifydownloader_default network.
MUSIC_FERRY_UNPLUG_HELPER_URL=http://172.19.0.1:17888
MUSIC_FERRY_UNPLUG_HELPER_TOKEN=replace-with-random-token
```

Get the correct gateway value for your current container network:

```bash
docker inspect -f '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}' music-ferry-web
```

If UFW is enabled, allow helper traffic only from this Docker bridge network:

```bash
sudo ufw allow in on br-<network-id-prefix> proto tcp \
  from <bridge-subnet> to <bridge-gateway-ip> port 17888 \
  comment 'music-ferry helper (docker only)'
```

Example from this setup:

```bash
sudo ufw allow in on br-f3b096331aab proto tcp \
  from 172.19.0.0/16 to 172.19.0.1 port 17888 \
  comment 'music-ferry helper (docker only)'
```

Apply changes:

```bash
docker compose --env-file .env.docker up -d --build
```

Security note: helper unmount is restricted to one path only (from
`paths.headphones_mount` in `config.yaml`, or `HELPER_ALLOWED_MOUNT`).

## Project Structure

```
music-ferry/
├── music_ferry/
│   ├── __init__.py
│   ├── config.py        # YAML config loading
│   ├── library.py       # Track/playlist persistence
│   ├── spotify_api.py   # Spotify playlist metadata
│   ├── browser.py       # Playwright automation
│   ├── recorder.py      # PipeWire/FFmpeg recording
│   ├── tagger.py        # MP3 ID3 tagging
│   ├── transfer.py      # Interactive headphone transfer
│   ├── notify.py        # Ntfy notifications
│   ├── orchestrator.py  # Main sync workflow
│   ├── cli.py           # Command-line interface
│   ├── youtube/
│   │   ├── __init__.py
│   │   └── downloader.py # yt-dlp wrapper
│   ├── web/             # Web UI (FastAPI)
│   │   ├── __init__.py
│   │   ├── app.py       # Application factory
│   │   ├── routes/      # API endpoints
│   │   ├── services/    # Business logic
│   │   └── static/      # Dashboard HTML/CSS/JS
│   └── metrics/         # Prometheus instrumentation
│       ├── __init__.py
│       ├── collectors.py
│       └── decorators.py
├── tests/               # Test suite
├── docs/                # Documentation
│   └── web-ui.md        # Web UI guide
├── scripts/
│   ├── NOTE.md          # Legacy script note
│   ├── install.sh       # Legacy host install helper
│   ├── install-systemd.sh # Legacy systemd timer installer
│   ├── install-systemd-web.sh # Legacy systemd web service installer
│   ├── headphones-mount.sh # Host helper to unlock/mount removable media
│   ├── headphones-unmount.sh # Host helper to unmount/lock removable media
│   └── uninstall.sh     # Legacy host uninstall helper
├── systemd/             # Systemd service files
│   └── music-ferry-web.service
└── pyproject.toml
```

## Development

```bash
# Activate development environment
source .venv/bin/activate

# Build package
make build

# Run tests
make test

# Lint and typecheck
make lint
make typecheck

# Format code
make format

# Install locally (non-editable) in .venv
make install

# Install locally (editable) in .venv for development
make install-dev

# Build and install the wheel into the local runtime venv
make install-release

# Run specific test file
pytest tests/test_config.py -v

# Run with coverage
pytest --cov=music_ferry
```

### Releasing a New Version

1. Update version in `pyproject.toml`
2. Commit and push changes
3. Create and push a tag:

```bash
git tag v0.2.0
git push origin v0.2.0
```

GitHub Actions will automatically:
- Run tests
- Build the package
- Create a GitHub Release with artifacts

### CI/CD

This project uses GitHub Actions for continuous integration:

- **CI workflow**: Runs tests on every push/PR (Python 3.11 & 3.12)
- **Release workflow**: Creates GitHub releases when tags are pushed

## How Recording Works

1. Fetches playlist metadata from Spotify API
2. Compares against local tracks database to find new tracks
3. If no new tracks exist, exits early without starting browser
4. Creates a PipeWire virtual sink with generic name
5. Launches headless Chromium with stealth features to avoid detection
6. Routes browser audio to the virtual sink
7. For each new track:
   - Navigates to the track on Spotify Web Player
   - Adds random delays to mimic human behavior
   - Starts FFmpeg recording from the sink's monitor source
   - Waits for the track duration (from API metadata)
   - Stops recording and tags with ID3 metadata

## Troubleshooting

### "Login expired" error

Run `music-ferry sync` manually to re-authenticate. Cookies are saved to `~/.music-ferry/cookies/`.

### No audio recorded

- Check PipeWire is running: `pactl info`
- Verify FFmpeg has PulseAudio support: `ffmpeg -formats | grep pulse`

### Headphones not detected

- Verify mount point in config matches actual mount path
- Check the Music folder exists on the headphones

### Browser issues

- Reinstall Playwright: `playwright install chromium`
- Check Xvfb is installed for headless operation

## License

MIT
