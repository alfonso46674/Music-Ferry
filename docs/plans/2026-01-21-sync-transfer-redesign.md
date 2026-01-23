# Sync & Transfer Redesign

Design document for separating download and transfer workflows, adding playlist tracking, and implementing intelligent playback modes.

## Goals

1. Separate automatic sync (download) from manual transfer (to headphones)
2. Track which playlists each song belongs to
3. Delete tracks when removed from all playlists
4. Intelligent playback: playlist mode vs individual track mode
5. Interactive transfer menu with multiple options

## Data Model

Replace `tracks.json` with enhanced `library.json`:

```json
{
  "version": 1,
  "tracks": {
    "4iV5W9uYEdYUVa79Axb7Rh": {
      "filename": "4iV5W9uYEdYUVa79Axb7Rh.mp3",
      "title": "Shape of You",
      "artist": "Ed Sheeran",
      "playlists": ["37i9dQZEVXcQ9COmYvdajy", "5Rrf7mqN8uus2AaQQQNdc1"]
    }
  },
  "playlists": {
    "37i9dQZEVXcQ9COmYvdajy": {
      "name": "Discover Weekly",
      "last_synced": "2026-01-21T06:23:00Z",
      "track_count": 30
    }
  }
}
```

Key points:
- Each track stores list of playlist IDs it belongs to
- Playlists section stores names and sync metadata
- Track is orphaned when `playlists` list becomes empty
- `version` field enables future schema migrations

## CLI Structure

```bash
# Automatic sync (runs at 5-8am via systemd)
music-ferry sync
music-ferry sync -v              # verbose
music-ferry sync -c /path/to/config.yaml

# Interactive transfer (run manually when headphones connected)
music-ferry transfer
music-ferry transfer -v
```

### Sync Command

Downloads new tracks and cleans up orphans. Never transfers to headphones.

Flow:
1. **Fetch**: Load local database, fetch all playlists from Spotify API
2. **Diff**: Identify new tracks, membership changes, orphaned tracks
3. **Download**: Record new tracks (browser only starts if needed)
4. **Cleanup**: Update memberships, delete orphaned tracks and MP3s
5. **Notify**: Send Ntfy notification with summary

### Transfer Command

Interactive menu when headphones are connected.

```
═══════════════════════════════════════════════════════
  Music Ferry - Transfer to Headphones
═══════════════════════════════════════════════════════

Headphones: /media/alfonso/HEADPHONES (connected)

Local Library:
  Discover Weekly      12 tracks (3 new)
  Workout Mix           8 tracks (1 new)
  ─────────────────────────────────
  Total                20 tracks (4 new)

On Headphones:
  16 tracks
  3 orphaned (no longer in playlists)

Actions:
  [1] Sync changes - add 4 new, remove 3 orphaned
  [2] Full reset - clear headphones, copy all 20 tracks
  [3] View details - show tracks by playlist
  [4] Cancel

Choose an option [1-4]:
```

View details shows tracks grouped by playlist:
```
Discover Weekly (12 tracks):
  ✓ Shape of You - Ed Sheeran
  ✓ Blinding Lights - The Weeknd
  + Flowers - Miley Cyrus (new)
  + Anti-Hero - Taylor Swift (new)
  ...

Orphaned (to be removed):
  ✗ Old Song - Some Artist
```

Legend: `✓` on headphones, `+` new, `✗` will be removed

## Playback Mode Selection

Choose between playlist mode and individual track mode based on how many tracks are new:

```
new_ratio = new_tracks / total_tracks

If new_ratio >= 0.7 (70% or more):
  → PLAYLIST MODE

If new_ratio < 0.7:
  → INDIVIDUAL MODE
```

### Playlist Mode

Used when most tracks are new (first sync, or playlists like Discover Weekly that refresh entirely).

1. Navigate to playlist page
2. Click play (starts from first track)
3. Monitor "now playing" element for track changes
4. For each track:
   - If new: start recording
   - If existing: let it play through (no recording)
5. Continue until all tracks have played

Slower but looks like genuine playlist listening.

### Individual Mode

Used when only a few new tracks in an otherwise synced playlist.

1. For each new track:
   - Navigate directly to track page
   - Play and record
   - Move to next track

Faster, used for incremental updates.

## Orphan Handling

A track is orphaned when removed from ALL playlists in the config.

- Track removed from one playlist but still in another → Keep it, update membership
- Track removed from all playlists → Delete MP3, remove from database
- Safety: If all playlists removed from config, don't auto-delete everything

## Headphones Tracking

Hybrid approach for data integrity and minimal flash wear:

1. **Scan headphones** each time to get actual file list (reads = no wear)
2. **Compare against local library** to compute diff
3. **Execute minimal operations** - only add/remove what's necessary
4. **Verify after transfer** - confirm success

No separate "headphones database" - filesystem is source of truth.

## Error Handling

### Playlist Mode Errors
- Track stuck / won't advance → Timeout after `track_duration + 30s`, skip
- Playback pauses → Detect and click play to resume
- Browser crash → Save progress, resume next run

### Sync Recovery
- Database saves after each track
- Missing MP3 for track in DB → Re-download
- Interrupted sync → Resume from last completed track

### Transfer Errors
- Headphones disconnected mid-transfer → Warn user, rsync is resumable
- Disk full → Check space before starting, show required vs available

## File Structure

```
~/.music-ferry/
├── config.yaml
├── library.json         # Enhanced track + playlist data
├── cookies/
│   └── spotify-session.json
└── music/
    └── *.mp3 files
```

## Files to Modify

| File | Changes |
|------|---------|
| `tracks_db.py` | Rename to `library.py`, enhanced data model with playlist membership |
| `orchestrator.py` | Separate sync logic, add playback mode selection |
| `browser.py` | Add playlist navigation, track change detection |
| `transfer.py` | Add interactive menu, orphan removal, filesystem scanning |
| `cli.py` | Add `sync` and `transfer` subcommands |

## Migration

On first run with new code:
1. Detect old `tracks.json` format
2. Migrate to `library.json` format
3. Set all existing tracks' playlist membership based on current API data
