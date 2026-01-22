# Spotify Swimmer

Download Spotify playlists to MP3 files for offline listening on waterproof headphones while swimming.

## How It Works

1. **Checks for new tracks** - compares playlist metadata against local database
2. **Skips fully-synced playlists** - only starts browser if there are new tracks
3. **Plays each new track** via browser automation (Spotify Web Player)
4. **Records the audio** from a virtual PipeWire sink using FFmpeg
5. **Tags MP3 files** with ID3 metadata (title, artist, album, cover art)
6. **Transfers to headphones** via USB mass storage using rsync
7. **Runs automatically** between 5-8am via systemd timer (randomized)
8. **Sends notifications** via Ntfy on success/failure

## Requirements

- Linux with PipeWire/PulseAudio
- Python 3.11+
- FFmpeg
- Xvfb (for headless browser)
- rsync

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/spotify-swimmer.git
cd spotify-swimmer

# Create virtual environment and install
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Install Playwright browser
playwright install chromium

# Run the install script
./scripts/install-systemd.sh
```

## Configuration

Edit `~/.spotify-swimmer/config.yaml`:

```yaml
spotify:
  client_id: "YOUR_SPOTIFY_CLIENT_ID"
  client_secret: "YOUR_SPOTIFY_CLIENT_SECRET"
  username: "YOUR_SPOTIFY_USERNAME"

playlists:
  - name: "Discover Weekly"
    url: "https://open.spotify.com/playlist/37i9dQZEVXcQ9COmYvdajy"
  - name: "Workout Mix"
    url: "https://open.spotify.com/playlist/YOUR_PLAYLIST_ID"

audio:
  bitrate: 192  # kbps
  format: "mp3"

paths:
  music_dir: "~/.spotify-swimmer/music"
  headphones_mount: "/media/yourusername/HEADPHONES"
  headphones_music_folder: "Music"

notifications:
  ntfy_topic: "your-secret-topic"
  ntfy_server: "https://ntfy.sh"
  notify_on_success: false
  notify_on_failure: true

behavior:
  skip_existing: true
  auto_transfer: true
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

## Usage

### Manual Run

```bash
# Run sync manually
spotify-swimmer

# With verbose logging
spotify-swimmer -v

# With custom config path
spotify-swimmer -c /path/to/config.yaml
```

### First Run (Login)

The first time you run, you'll need to log into Spotify:

1. Run `spotify-swimmer` manually
2. The browser will open (or check logs for any login prompts)
3. Cookies are saved for future automated runs

### Automatic Scheduling

The installer sets up a systemd timer to run daily between 5-8am (randomized):

```bash
# Enable the timer
systemctl --user enable --now spotify-swimmer.timer

# Check timer status
systemctl --user list-timers spotify-swimmer.timer

# View logs
journalctl --user -u spotify-swimmer.service -f

# Run manually via systemd
systemctl --user start spotify-swimmer.service

# Disable the timer
systemctl --user disable spotify-swimmer.timer
```

## Project Structure

```
spotify-swimmer/
├── spotify_swimmer/
│   ├── __init__.py
│   ├── config.py        # YAML config loading
│   ├── spotify_api.py   # Playlist metadata fetching
│   ├── browser.py       # Playwright automation
│   ├── recorder.py      # PipeWire/FFmpeg recording
│   ├── tagger.py        # MP3 ID3 tagging
│   ├── transfer.py      # USB headphone transfer
│   ├── notify.py        # Ntfy notifications
│   ├── orchestrator.py  # Main sync workflow
│   └── cli.py           # Command-line interface
├── tests/               # Test suite (39 tests)
├── bin/
│   └── sync.sh          # Systemd entry point
├── systemd/
│   ├── spotify-swimmer.service
│   └── spotify-swimmer.timer
├── scripts/
│   └── install-systemd.sh
└── pyproject.toml
```

## Development

```bash
# Run tests
pytest -v

# Run specific test file
pytest tests/test_config.py -v

# Install in development mode
pip install -e ".[dev]"
```

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

Run `spotify-swimmer` manually to re-authenticate. Cookies are saved to `~/.spotify-swimmer/cookies/`.

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
