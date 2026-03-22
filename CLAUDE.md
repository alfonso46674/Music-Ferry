# Music Ferry — CLAUDE.md

## Project Overview

**music-ferry** ferries music from Spotify and YouTube to local MP3 files and transfers them to headphones.

- Records Spotify audio via Playwright browser automation + PulseAudio virtual sink + ffmpeg
- Downloads YouTube playlists via yt-dlp (no browser needed)
- Tracks downloaded tracks/playlists in a JSON library (`library.json`)
- Transfers MP3s to headphones via file copy
- Exposes a FastAPI web dashboard with scheduled sync, live logs, and headphone management
- Deployed as a Docker Compose stack

## Key Commands

```bash
make test          # Run test suite
make lint          # Ruff linter
make typecheck     # mypy (strict)
make format        # black
black --check .    # Verify formatting without rewriting files
make check         # lint + typecheck + test

pytest tests/test_<name>.py -v   # Single test file

docker compose --env-file .env.docker up -d --build   # Start/rebuild
```

## Architecture

See [`coding-conventions.md`](coding-conventions.md) for patterns and anti-patterns.

```
music_ferry/
├── cli.py            # Entry point — argparse + command dispatch
├── config.py         # YAML config → dataclasses
├── library.py        # JSON persistence for tracks/playlists
├── orchestrator.py   # Main sync workflow (Spotify + YouTube)
├── browser.py        # Playwright automation (Spotify Web Player)
├── recorder.py       # PulseAudio virtual sink + ffmpeg recording
├── tagger.py         # ID3 metadata tagging (mutagen)
├── transfer.py       # Headphone file transfer logic
├── notify.py         # Ntfy push notifications
├── spotify_api.py    # Spotify metadata via spotipy
├── youtube/          # yt-dlp wrapper
└── web/              # FastAPI web UI
    ├── app.py        # Application factory + lifespan
    ├── routes/       # HTTP handlers (api, logs, metrics)
    └── services/     # Business logic (sync, library, headphones, scheduler)
```

## Testing Notes

- `make check` is the expected pre-merge baseline: lint + mypy + full test suite
- Web API tests use `httpx.AsyncClient` with `ASGITransport`, not FastAPI `TestClient`
- Routes that offload blocking work with `run_in_executor()` are often tested by calling the route coroutine directly with a stubbed loop
- New features or behavior changes are expected to ship with corresponding tests

## Known Issues / Audit

See [`docs/plans/2026-03-07-code-audit.md`](docs/plans/2026-03-07-code-audit.md) for a full bug audit conducted on 2026-03-07, covering critical bugs, medium issues, and code quality items.

## Headphones Safe Unplug

- Dockerized unmount uses host helper fallback (`/api/v1/headphones/prepare-unplug`)
- Helper is restricted to configured `paths.headphones_mount`
- See [`docs/web-ui.md`](docs/web-ui.md) and external runbook:
  `/home/alfonso/docs/projects/music-ferry/safe-unplug-hardening.md`

## Data Paths

```
~/.music-ferry/
├── config.yaml
├── cookies/         # Spotify session cookies (plain JSON)
├── spotify/library.json  # Track/playlist DB
├── spotify/music/   # MP3 files
├── youtube/library.json
├── youtube/music/
└── web_schedule.json  # Persisted scheduler settings
```

## Environment

- Python 3.11+ (venv at `.venv/`)
- Dev deps: black, ruff, mypy, pytest, pytest-asyncio, httpx
- Runtime deps: ffmpeg, pactl/PulseAudio, rsync, Xvfb (headless browser)
- Config: `config.yaml` (default: `~/.music-ferry/config.yaml`)
