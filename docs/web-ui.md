# Music Ferry Web UI

Music Ferry includes a built-in web UI for monitoring your library, triggering syncs, managing headphones transfer, and viewing logs.

## Quick Start (Docker Compose)

To run web UI + API in Docker:

```bash
cp .env.docker.example .env.docker
docker compose --env-file .env.docker up -d --build
```

The dashboard will be available at `http://127.0.0.1:4444`.

Note: headphone transfer in Docker requires host removable-media paths to be bind-mounted.
The provided `docker-compose.yml` mounts `/media` and `/run/media` with mount propagation,
so re-mounted headphones become visible without restarting containers.

### Local Development (optional)

```bash
# Start local web server (non-Docker development)
music-ferry serve

# Custom port
music-ferry serve --port 8080

# Auto-reload
music-ferry serve --reload
```

## Features

### Dashboard

The web UI provides a real-time dashboard showing:

- **Sync Status**: Whether a sync is running, last sync time
- **Schedule Control**: Enable/disable automatic sync, set time, and choose source
- **Library Summary**: Track counts, playlist counts, and total size for Spotify and YouTube
- **Headphones Control**: Scan mount points, prepare accessibility, and transfer to selected device
- **Live Logs**: Streaming log output via Server-Sent Events

### REST API

All data is available via a REST API at `/api/v1/`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/status` | GET | Current sync status |
| `/api/v1/library` | GET | Library summary (all sources) |
| `/api/v1/library/{source}` | GET | Detailed library for spotify/youtube |
| `/api/v1/config` | GET | Configuration (secrets redacted) |
| `/api/v1/sync` | POST | Trigger a sync operation |
| `/api/v1/schedule` | GET | Read automatic sync schedule |
| `/api/v1/schedule` | POST | Update automatic sync schedule |
| `/api/v1/sync/{job_id}` | GET | Get sync job status |
| `/api/v1/headphones/scan` | GET | Scan connected/configured headphone mount points |
| `/api/v1/headphones/access` | POST | Ensure selected mount has accessible music folder |
| `/api/v1/headphones/transfer` | POST | Transfer selected source(s) to selected mount |
| `/api/v1/headphones/delete-mp3` | POST | Delete `.mp3` files from selected mount's music folder |
| `/api/v1/headphones/prepare-unplug` | POST | Sync and safely unmount selected mount |
| `/api/v1/logs/stream` | GET | SSE stream of log lines |

### Prometheus Metrics

Metrics are exposed at `/metrics` for Prometheus scraping:

**Library Metrics (gauges):**
- `music_ferry_tracks_total{source}` - Total tracks per source
- `music_ferry_playlists_total{source}` - Total playlists per source
- `music_ferry_library_size_bytes{source}` - Library size in bytes

**Sync Metrics (counters/histograms):**
- `music_ferry_sync_total{source,status}` - Sync operations count
- `music_ferry_sync_duration_seconds{source}` - Sync duration histogram
- `music_ferry_tracks_downloaded_total{source}` - Tracks downloaded count
- `music_ferry_sync_last_success_timestamp{source}` - Last successful sync

**Process Metrics (from prometheus_client):**
- `process_cpu_seconds_total`
- `process_resident_memory_bytes`

## CLI Options

```bash
music-ferry serve [OPTIONS]

Options:
  --host TEXT     Host to bind to (default: 127.0.0.1)
  --port INTEGER  Port to listen on (default: 4444)
  --reload        Enable auto-reload for development
```

## Security

The web UI has **no authentication** - it's designed to be accessed only from trusted networks:

- Bind to `127.0.0.1` by default (localhost only)
- Use a reverse proxy with Tailscale/VPN for remote access
- Do not expose directly to the internet

## Deployment

### Docker Compose

```bash
# Start or rebuild
docker compose --env-file .env.docker up -d --build

# View logs
docker compose --env-file .env.docker logs -f web

# Check status
docker compose --env-file .env.docker ps

# Stop
docker compose --env-file .env.docker down
```

### Host Safe-Unplug Helper (Optional, Recommended)

In Docker, unmount can require host privileges. If `Prepare Safe Unplug` reports a
permission error, run the host helper as a root systemd service and point the web
container to it.
The helper is restricted to a single mount path (from `paths.headphones_mount`
in your `config.yaml`, or `HELPER_ALLOWED_MOUNT` if explicitly set).

1. Install and start helper service:

```bash
sudo cp systemd/music-ferry-unplug-helper.service /etc/systemd/system/
sudo tee /etc/default/music-ferry-unplug-helper >/dev/null <<'EOF'
HELPER_BIND=0.0.0.0
HELPER_PORT=17888
# Set a random token and reuse it in .env.docker
HELPER_TOKEN=replace-with-random-token
# Optional override (otherwise helper reads paths.headphones_mount from config):
# HELPER_ALLOWED_MOUNT=/media/alfonso/681B-7309
HELPER_CONFIG_PATH=/home/alfonso/.music-ferry/config.yaml
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now music-ferry-unplug-helper.service
sudo systemctl status music-ferry-unplug-helper.service --no-pager
```

2. Configure web container env (`.env.docker`):

```bash
# Use the web container's network gateway IP for helper routing.
# Example shown for spotifydownloader_default network.
MUSIC_FERRY_UNPLUG_HELPER_URL=http://172.19.0.1:17888
MUSIC_FERRY_UNPLUG_HELPER_TOKEN=replace-with-random-token
```

3. Discover gateway + apply firewall rule (if UFW is enabled):

```bash
# Gateway used by web container network:
docker inspect -f '{{range .NetworkSettings.Networks}}{{.Gateway}}{{end}}' music-ferry-web

# Tight UFW rule for helper port, Docker bridge only:
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

4. Rebuild web container:

```bash
docker compose --env-file .env.docker up -d --build
```

### Reverse Proxy (Caddy)

To access the web UI through Caddy:

```caddy
# Caddyfile
handle_path /music-ferry/* {
    reverse_proxy 127.0.0.1:4444 {
        flush_interval -1  # Required for SSE log streaming
    }
}
```

The `handle_path` directive automatically strips the `/music-ferry` prefix before forwarding to the backend.

### Reverse Proxy (nginx)

To access the web UI through nginx:

```nginx
# /etc/nginx/sites-available/music-ferry
location /music-ferry/ {
    proxy_pass http://127.0.0.1:4444/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Required for SSE log streaming
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_cache off;
}
```

### Prometheus Configuration

Add Music Ferry to your Prometheus scrape config:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'music-ferry'
    static_configs:
      - targets: ['127.0.0.1:4444']
    metrics_path: /metrics
    scrape_interval: 30s
```

## API Examples

### Check Status

```bash
curl http://localhost:4444/api/v1/status
```

Response:
```json
{
  "syncing": false,
  "last_sync": "2024-01-26T10:30:00.000000",
  "next_scheduled": null,
  "current_job_id": null
}
```

### Get Library Summary

```bash
curl http://localhost:4444/api/v1/library
```

Response:
```json
{
  "spotify": {
    "tracks": 150,
    "playlists": 3,
    "size_bytes": 450000000,
    "enabled": true
  },
  "youtube": {
    "tracks": 25,
    "playlists": 1,
    "size_bytes": 100000000,
    "enabled": true
  },
  "total": {
    "tracks": 175,
    "playlists": 4,
    "size_bytes": 550000000
  }
}
```

### Trigger Sync

```bash
curl -X POST http://localhost:4444/api/v1/sync
```

Response:
```json
{
  "job_id": "a1b2c3d4",
  "status": "started"
}
```

### Configure Schedule

```bash
curl -X POST http://localhost:4444/api/v1/schedule \
  -H 'Content-Type: application/json' \
  -d '{"enabled": true, "time": "05:30", "source": "youtube"}'
```

Response:
```json
{
  "enabled": true,
  "time": "05:30",
  "source": "youtube",
  "next_run": "2024-01-27T05:30:00"
}
```

### Check Sync Progress

```bash
curl http://localhost:4444/api/v1/sync/a1b2c3d4
```

Response:
```json
{
  "job_id": "a1b2c3d4",
  "status": "completed",
  "started_at": "2024-01-26T10:30:00.000000",
  "completed_at": "2024-01-26T10:35:00.000000",
  "result": {
    "total_tracks": 5,
    "is_success": true,
    "playlists": [
      {"name": "Discover Weekly", "tracks_synced": 5, "error": null}
    ]
  }
}
```

### Stream Logs

```bash
curl http://localhost:4444/api/v1/logs/stream
```

Response (SSE stream):
```
event: log
data: 2024-01-26 10:30:00 - music_ferry - INFO - Starting sync...

event: log
data: 2024-01-26 10:30:01 - music_ferry - INFO - Processing playlist: Discover Weekly
```

### Get Prometheus Metrics

```bash
curl http://localhost:4444/metrics
```

Response:
```
# HELP music_ferry_tracks_total Total number of tracks in library
# TYPE music_ferry_tracks_total gauge
music_ferry_tracks_total{source="spotify"} 150.0
music_ferry_tracks_total{source="youtube"} 25.0
...
```

## Resource Usage

The web UI is designed to be lightweight:

- **RAM at idle**: ~20-30 MB
- **RAM during sync**: ~40-50 MB (orchestrator overhead)
- **Docker Compose limit**: 256 MB max (see `docker-compose.yml`)
- **No database**: Uses existing JSON library files

## Troubleshooting

### Server won't start

Check if the port is already in use:
```bash
lsof -i :4444
```

### SSE logs not streaming

Ensure your reverse proxy has buffering disabled:
```nginx
proxy_buffering off;
```

### Metrics not updating

Library metrics are refreshed on each `/metrics` scrape. If values seem stale, check that the library.json files exist and are readable.
