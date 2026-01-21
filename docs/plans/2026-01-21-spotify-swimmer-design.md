# Spotify Swimmer - Design Document

**Date**: 2026-01-21
**Purpose**: Download Spotify playlists to waterproof headphones for offline swimming

## Problem

Waterproof headphones with local storage need music files transferred manually. Bluetooth doesn't work underwater, so streaming isn't an option. The goal is to automate downloading music from Spotify playlists by recording playback (avoiding ToS violations) and transferring MP3s to headphones.

## Solution Overview

A Python application that:
1. Fetches playlist metadata from Spotify API
2. Plays songs via browser automation (Spotify Web Player)
3. Records audio output to MP3 files
4. Transfers files to USB-mounted headphones
5. Runs automatically at 3am via systemd timer
6. Sends notifications via Ntfy on success/failure

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Systemd Timer (3am)                      │
└─────────────────────┬───────────────────────────────────────┘
                      │ triggers
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Main Orchestrator Script                  │
│  1. Load config (playlists, paths, credentials)             │
│  2. For each playlist:                                       │
│     - Fetch metadata from Spotify API                       │
│     - Determine which songs are new                         │
│     - Record new songs via browser automation               │
│  3. Transfer MP3s to headphones (if mounted)                │
│  4. Send success/failure notification via Ntfy              │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

- **Config file** (YAML) - Spotify credentials, playlist URLs, paths, Ntfy topic
- **Spotify API client** - Fetches playlist tracks and metadata (no playback, just data)
- **Browser automation** - Playwright controlling Spotify Web Player
- **Audio recorder** - PipeWire/FFmpeg capturing browser audio output
- **File manager** - Handles MP3 tagging, organization, transfer to USB

---

## Recording Flow

```
1. SETUP PHASE
   ├─ Create PipeWire virtual sink ("spotify-capture")
   ├─ Launch headless browser (Playwright + Chromium)
   ├─ Route browser audio → virtual sink
   └─ Log into Spotify Web Player (stored session/cookies)

2. FOR EACH PLAYLIST
   ├─ Fetch track list from Spotify API
   ├─ Filter out already-downloaded tracks (by Spotify track ID)
   ├─ Navigate browser to playlist
   └─ For each NEW track:
       ├─ Start FFmpeg recording from virtual sink
       ├─ Click play on specific track
       ├─ Wait for track duration (from API metadata)
       ├─ Stop recording
       ├─ Encode to MP3 @ 192kbps
       └─ Tag with metadata (title, artist, album, cover art)

3. CLEANUP
   ├─ Close browser
   ├─ Remove virtual sink
   └─ Update local database of downloaded track IDs
```

### Timing

- Track duration comes from Spotify API metadata (known upfront)
- Add ~2 seconds buffer at start of recording
- Trim silence from beginning/end of each recording

### Track Database

A simple JSON file mapping Spotify track IDs to local filenames. Used to determine what's already downloaded and skip re-recording.

---

## File Storage & Transfer

### Local Storage Structure

```
~/.spotify-swimmer/
├── config.yaml              # Configuration file
├── tracks.json              # Database of downloaded tracks
├── cookies/                 # Browser session data
│   └── spotify-session.json
├── music/                   # Downloaded MP3s
│   ├── 4iV5W9uYEdYUVa79Axb7Rh.mp3
│   ├── 1301WleyT98MSxVHPZCA6M.mp3
│   └── ...
└── logs/
    └── sync.log
```

### Filename Format

`{spotify_track_id}.mp3`
- Using track ID avoids issues with special characters in song titles
- Human-readable info stored in MP3 ID3 tags (artist, title, album)
- Music player shows the tags, not the filename

### Transfer to Headphones

```
1. Detect if headphones mounted (check configured mount point)
2. If mounted:
   ├─ Copy all MP3s from ~/.spotify-swimmer/music/ to /mount/Music/
   ├─ Use rsync for efficiency (only copies new/changed files)
   └─ Safely unmount when done
3. If not mounted:
   └─ Log warning, skip transfer, still send notification
```

### MP3 Tags Applied

- Title, Artist, Album
- Track artwork (downloaded via Spotify API)
- Year, Genre (if available)

### File Organization

Flat folder on headphones - all MP3s in one `/Music/` folder. Simple and universally compatible.

---

## Configuration

```yaml
# ~/.spotify-swimmer/config.yaml

spotify:
  client_id: "your_spotify_app_client_id"
  client_secret: "your_spotify_app_client_secret"
  username: "your_spotify_username"
  # Password handled via browser cookies, not stored in config

playlists:
  - name: "Discover Weekly"
    url: "https://open.spotify.com/playlist/37i9dQZEVXcQ9COmYvdajy"
  - name: "Workout Mix"
    url: "https://open.spotify.com/playlist/xxxxxxxxxxxxx"

audio:
  bitrate: 192  # kbps
  format: "mp3"

paths:
  music_dir: "~/.spotify-swimmer/music"
  headphones_mount: "/media/alfonso/HEADPHONES"
  headphones_music_folder: "Music"  # folder on headphones

notifications:
  ntfy_topic: "my-secret-swimmer-topic"
  ntfy_server: "https://ntfy.sh"  # or self-hosted
  notify_on_success: false
  notify_on_failure: true

behavior:
  skip_existing: true
  auto_transfer: true  # transfer to headphones if mounted
  trim_silence: true   # trim silence from start/end of recordings
```

### Notes

- **Spotify API credentials**: Create a free Spotify Developer app to get these. Only used for reading playlist metadata, not for playback.
- **Ntfy topic**: Should be a random/secret string so only you receive notifications.

---

## Scheduling with Systemd

### Service Unit

```ini
# ~/.config/systemd/user/spotify-swimmer.service

[Unit]
Description=Spotify Swimmer - Download playlists for offline swimming
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/home/alfonso/.spotify-swimmer/bin/sync.sh
Environment=DISPLAY=:99
TimeoutStartSec=3600  # 1 hour max runtime

[Install]
WantedBy=default.target
```

### Timer Unit

```ini
# ~/.config/systemd/user/spotify-swimmer.timer

[Unit]
Description=Run Spotify Swimmer daily at 3am

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true  # Run on boot if we missed 3am

[Install]
WantedBy=timers.target
```

### Key Behaviors

- Runs as user service (no root needed)
- `Persistent=true` means if machine was off at 3am, it runs when you boot
- 1 hour timeout prevents runaway processes
- Virtual display (`:99` via Xvfb) for headless browser operation

### Commands

```bash
# Enable automatic scheduling
systemctl --user enable spotify-swimmer.timer
systemctl --user start spotify-swimmer.timer

# Check when next run is scheduled
systemctl --user list-timers spotify-swimmer.timer

# Run manually (for testing or immediate sync)
systemctl --user start spotify-swimmer.service

# View logs
journalctl --user -u spotify-swimmer.service -f

# Disable scheduling
systemctl --user stop spotify-swimmer.timer
systemctl --user disable spotify-swimmer.timer
```

---

## Error Handling

| Scenario | Action |
|----------|--------|
| Spotify login expired | Notify via Ntfy, log error, exit |
| Playlist not found / private | Skip playlist, continue with others, notify |
| Network failure mid-recording | Retry track 2x, then skip and notify |
| FFmpeg crash | Log error, skip track, continue |
| Headphones not mounted | Complete recording, skip transfer, notify |
| Disk full | Stop immediately, notify |
| Browser crash | Restart browser, retry from current track |

---

## Notifications

Notifications sent via Ntfy with per-playlist breakdown.

### Success (if enabled)

```
Title: 🏊 Spotify Swimmer Complete
Body:
Synced 12 new tracks. Transferred to headphones.

Playlists:
• Discover Weekly: 8 new tracks
• Workout Mix: 4 new tracks
```

### Partial Success

```
Title: ⚠️ Spotify Swimmer Partial
Body:
Synced 5 new tracks. Some issues occurred.

Playlists:
• Discover Weekly: 5 new tracks
• Workout Mix: Failed (playlist not found)

Transferred to headphones.
```

### Failure

```
Title: ❌ Spotify Swimmer Failed
Body:
Login expired - please re-authenticate.

Playlists:
• Discover Weekly: Not synced
• Workout Mix: Not synced
```

### Logging

- All output goes to stdout/stderr (captured by journalctl)
- Detailed logs in `~/.spotify-swimmer/logs/sync.log`
- Log rotation: keep last 7 days

---

## Tech Stack

### Language

Python - rich ecosystem for Spotify API, browser automation, audio processing

### Python Dependencies

```
playwright          # Browser automation (Chromium)
spotipy             # Spotify Web API client
ffmpeg-python       # Audio recording & encoding (wraps FFmpeg)
mutagen             # MP3 ID3 tag writing
pyyaml              # Config file parsing
requests            # Ntfy notifications
```

### System Requirements

```
ffmpeg              # Audio encoding
xvfb                # Virtual display for headless browser
pipewire            # Audio routing
```

---

## Project Structure

```
spotify-swimmer/
├── spotify_swimmer/
│   ├── __init__.py
│   ├── config.py        # Config loading & validation
│   ├── spotify_api.py   # Playlist metadata fetching
│   ├── browser.py       # Playwright automation
│   ├── recorder.py      # PipeWire/FFmpeg recording
│   ├── tagger.py        # MP3 metadata tagging
│   ├── transfer.py      # USB headphone transfer
│   └── notify.py        # Ntfy notifications
├── bin/
│   └── sync.sh          # Entry point for systemd
├── tests/
├── pyproject.toml
└── README.md
```

---

## Future Considerations

- **Raspberry Pi deployment**: Could run on a dedicated Pi as a "music sync station"
- **Web UI**: Simple status page showing last sync, upcoming schedule
- **Multiple headphone support**: Different playlists for different devices
