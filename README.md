# Spotify Swimmer

[![CI](https://github.com/yourusername/spotify-swimmer/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/spotify-swimmer/actions/workflows/ci.yml)

Download Spotify and YouTube playlists to MP3 files for offline listening on waterproof headphones while swimming.

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
10. **Runs automatically** between 5-8am via systemd timer (randomized)
11. **Transfer on demand** - manual command to transfer to headphones
12. **Sends notifications** via Ntfy on success/failure

## Requirements

- Linux with PipeWire/PulseAudio
- Python 3.11+
- FFmpeg
- Xvfb (for headless browser)
- rsync

## Installation

### Quick Install (recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/spotify-swimmer.git
cd spotify-swimmer

# Install the package (uses pipx if available, otherwise pip --user)
./scripts/install.sh

# Install Playwright browser for Spotify
playwright install chromium

# (Optional) Set up automatic scheduling
./scripts/install-systemd.sh
```

### Development Install

```bash
# Clone and create virtual environment
git clone https://github.com/yourusername/spotify-swimmer.git
cd spotify-swimmer
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Install Playwright browser
playwright install chromium
```

### Uninstall

```bash
./scripts/uninstall.sh
```

### Updating

**Check your install type:**
```bash
pip show spotify-swimmer | grep Location
# If Location is your project folder → editable install
# If Location is site-packages → regular install
```

**After making code changes:**

| Install Type | Action Needed |
|--------------|---------------|
| Editable (`pip install -e .`) | Nothing - changes apply immediately |
| Regular (`pip install .`) | Reinstall: `pip install .` |
| pipx | Reinstall: `pipx install --force .` |

**Switching install modes:**
```bash
# Switch to editable (for development)
pip install -e ".[dev]"

# Switch to regular (for release/freeze)
pip install .

# No need to uninstall first - it overwrites automatically
```

**Systemd timer:** No changes needed when updating code. The timer just runs the `spotify-swimmer` command, which uses whatever version is currently installed.

## Configuration

Edit `~/.spotify-swimmer/config.yaml`:

```yaml
spotify:
  enabled: true
  client_id: "YOUR_SPOTIFY_CLIENT_ID"
  client_secret: "YOUR_SPOTIFY_CLIENT_SECRET"
  username: "YOUR_SPOTIFY_USERNAME"
  playlists:
    - name: "Discover Weekly"
      url: "https://open.spotify.com/playlist/37i9dQZEVXcQ9COmYvdajy"
    - name: "Workout Mix"
      url: "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID"

youtube:
  enabled: false
  playlists:
    - name: "Coding Music"
      url: "https://www.youtube.com/playlist?list=YOUR_PLAYLIST_ID"

audio:
  bitrate: 192  # kbps
  format: "mp3"

paths:
  music_dir: "~/.spotify-swimmer"
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
3. Run `spotify-swimmer sync` or `spotify-swimmer sync --youtube`

**Source flags:**

- `--spotify` - sync/transfer only Spotify tracks
- `--youtube` - sync/transfer only YouTube tracks
- No flag - sync/transfer both sources (default)

**Directory structure:**

Tracks are organized by source:
```
~/.spotify-swimmer/
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

Spotify Swimmer has two separate commands:

- **`sync`** - Downloads new tracks and cleans up orphaned files
- **`transfer`** - Interactive menu to transfer music to headphones

```bash
# Sync both Spotify and YouTube (default)
spotify-swimmer sync

# Sync only Spotify
spotify-swimmer sync --spotify

# Sync only YouTube
spotify-swimmer sync --youtube

# Transfer all tracks to headphones
spotify-swimmer transfer

# Transfer only Spotify tracks
spotify-swimmer transfer --spotify

# With verbose logging
spotify-swimmer -v sync

# With custom config path
spotify-swimmer -c /path/to/config.yaml sync
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

### First Run (Login)

The first time you run, you'll need to log into Spotify:

1. Run `spotify-swimmer sync` manually
2. The browser will open (or check logs for any login prompts)
3. Cookies are saved for future automated runs

### Automatic Scheduling

Install the systemd timer for automatic daily syncs:

```bash
# Install systemd units
./scripts/install-systemd.sh

# Enable the timer
systemctl --user enable --now spotify-swimmer.timer

# Check timer status
systemctl --user list-timers spotify-swimmer.timer

# View logs
journalctl --user -u spotify-swimmer.service -f

# Run sync manually via systemd
systemctl --user start spotify-swimmer.service

# Disable the timer
systemctl --user disable spotify-swimmer.timer
```

Transfer is always manual (your headphones may not be connected during automated runs).

## Project Structure

```
spotify-swimmer/
├── spotify_swimmer/
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
│   └── youtube/
│       ├── __init__.py
│       └── downloader.py # yt-dlp wrapper
├── tests/               # Test suite (117 tests)
├── scripts/
│   ├── install.sh       # Install package
│   ├── install-systemd.sh # Install systemd timer
│   └── uninstall.sh     # Uninstall everything
└── pyproject.toml
```

## Development

```bash
# Activate development environment
source .venv/bin/activate

# Run tests
pytest -v

# Run specific test file
pytest tests/test_config.py -v

# Run with coverage
pytest --cov=spotify_swimmer
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

Run `spotify-swimmer sync` manually to re-authenticate. Cookies are saved to `~/.spotify-swimmer/cookies/`.

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
