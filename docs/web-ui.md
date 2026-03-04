# Music Ferry Web UI

Music Ferry includes a built-in web UI for monitoring your library, triggering syncs, and viewing logs.

## Quick Start

```bash
# Start the web server
music-ferry serve

# Or with custom port
music-ferry serve --port 8080

# Development mode with auto-reload
music-ferry serve --reload
```

The dashboard will be available at `http://127.0.0.1:4444`

## Features

### Dashboard

The web UI provides a real-time dashboard showing:

- **Sync Status**: Whether a sync is running, last sync time
- **Library Summary**: Track counts, playlist counts, and total size for Spotify and YouTube
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
| `/api/v1/sync/{job_id}` | GET | Get sync job status |
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

### Systemd Service

Install the web UI as a systemd user service for automatic startup:

```bash
# Run the install script
./scripts/install-systemd-web.sh
```

Or manually:

```bash
# Copy service file
mkdir -p ~/.config/systemd/user
cp systemd/music-ferry-web.service ~/.config/systemd/user/

# Enable and start
systemctl --user daemon-reload
systemctl --user enable --now music-ferry-web.service

# Check status
systemctl --user status music-ferry-web.service

# View logs
journalctl --user -u music-ferry-web.service -f
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
- **Systemd limit**: 64 MB max
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
