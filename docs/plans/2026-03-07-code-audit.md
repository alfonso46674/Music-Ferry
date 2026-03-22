# Code Audit — 2026-03-07

Full audit of the music-ferry codebase. Findings are grouped by severity.

---

## Critical Bugs

### 1. `tagger.py:11-16` — `ID3NoHeaderError` handler re-raises immediately

```python
try:
    audio = MP3(mp3_path)
except ID3NoHeaderError:
    audio = MP3(mp3_path)  # BUG: same call raises again
    audio.add_tags()
```

The `except` block calls `MP3(mp3_path)` again — this re-raises `ID3NoHeaderError` on the same file.
Should use `mutagen.File` or create an empty MP3 object instead of re-calling `MP3`.

**Impact**: Tags are never written for MP3 files without an ID3 header; exception propagates up uncaught.

**Status (verified 2026-03-22)**: Fixed in commit `23810a9` (`fix(tagger): create ID3 tags when header is missing`). `music_ferry/tagger.py` now loads existing ID3 tags directly and creates a fresh `ID3()` object when the file has no header, instead of re-calling `MP3(mp3_path)`.

---

### 2. `cli.py` — `--spotify`/`--youtube` flags silently ignored

`_resolve_sources()` is defined and the flags are added to the parsers, but `main()` never calls `_resolve_sources()` and never passes the result to `cmd_sync` or `cmd_transfer`.

```python
# main() calls:
return cmd_sync(config, args.verbose)         # args.spotify/youtube never used
return cmd_transfer(config, args.verbose, args.auto)  # same

# Neither cmd_sync nor cmd_transfer receives source flags
```

Both commands always sync/transfer all sources regardless of `--spotify`/`--youtube`.

**Impact**: Documented CLI flags are completely non-functional.

**Status (verified 2026-03-22)**: Fixed in commit `6800313` (`fix(cli): honor selected sync and transfer sources`). `main()` now resolves the CLI source flags and passes them through to both `Orchestrator.run()` and `InteractiveTransfer`.

---

### 3. `library.py:87-114` — Non-atomic file writes

`save()` writes directly to `library.json` with `open(self.db_path, "w")`. A crash, OOM kill, or `KeyboardInterrupt` during the write leaves a truncated/corrupt JSON file with no recovery path.

**Impact**: Permanent library corruption on unexpected process termination.

**Status (verified 2026-03-22)**: Fixed in commit `98cd6b2` (`fix(library): save library.json atomically`). `Library.save()` now writes to a temp file in the target directory, flushes and `fsync()`s it, then atomically replaces `library.json`.

---

### 4. `orchestrator.py:441, 519` — Empty string `""` added as playlist_id

`_record_track()` and `_record_current_track()` both call:
```python
self.spotify_library.add_track(track.id, ..., "")
```

This adds `""` to `track.playlists`. While `_update_playlist_membership()` later adds the real playlist_id, the `""` entry is never removed. Tracks end up with `playlists = ["", "real_id"]`.

**Impact**: The orphan detection (`is_orphaned = len(playlists) == 0`) still works (not zero), but the library is polluted with garbage entries, and any code iterating `track.playlists` will encounter the empty string.

**Status (verified 2026-03-22)**: Fixed in commit `05b8f21` (`fix(orchestrator): persist spotify playlist ids correctly`). The Spotify recording helpers now receive the real `playlist_id` and store it directly instead of adding an empty string placeholder.

---

## Medium Bugs

### 5. `recorder.py:34-46` — Silent failure when virtual sink creation fails

```python
result = subprocess.run(["pactl", "load-module", ...], capture_output=True, text=True)
if result.returncode == 0:
    self._module_id = int(result.stdout.strip())
# No else/raise — failure is silently ignored
```

If `pactl` fails, `self._module_id` stays `None`, the sink doesn't exist, and ffmpeg records silence (or fails). No exception is raised to abort the sync.

**Impact**: Silent bad recordings on systems where PulseAudio setup fails.

**Status (verified 2026-03-22)**: Fixed in commit `6149dbc` (`fix(recorder): fail fast when sink creation fails`). `AudioRecorder.create_virtual_sink()` now raises on non-zero `pactl` exit codes and malformed module ids instead of silently continuing.

---

### 6. `recorder.py:85-91` — Unhandled `subprocess.TimeoutExpired`

```python
self._ffmpeg_process.terminate()
self._ffmpeg_process.wait(timeout=5)  # raises TimeoutExpired if ffmpeg hangs
```

`TimeoutExpired` is not caught. If ffmpeg hangs (e.g., blocked on audio), this propagates up through `__exit__`, potentially leaving the virtual sink un-destroyed.

**Impact**: Resource leak (dangling pactl module) on hung ffmpeg process.

**Status (verified 2026-03-22)**: Fixed in commit `a95b677` (`Fix linter and format issues in the tests`). `music_ferry/recorder.py` now catches `subprocess.TimeoutExpired`, logs a warning, kills ffmpeg, and waits for process exit.

---

### 7. `sync_service.py:313-317` — Dead code in `_compute_next_scheduled_time`

```python
if now <= today_target:
    return today_target
return today_target  # identical — dead branch
```

The last two cases return the same value. The intent when `now > today_target` (missed the window today, haven't run yet) is unclear: returning a past time triggers an immediate run, which may be correct but isn't documented. The dead code also masks the logic.

**Status (verified 2026-03-22)**: Fixed in commit `a95b677` (`Fix linter and format issues in the tests`). The final branch now returns `today_target + timedelta(days=1)` instead of the same-day past timestamp.

---

## Code Quality

### 8. `notify.py:103` — Silent exception swallowing

```python
except Exception:
    pass  # Don't let notification failures crash the app
```

The intent is correct (don't crash), but failures are invisible. Should log:
```python
except Exception as exc:
    logger.warning("Failed to send notification: %s", exc)
```

**Status (verified 2026-03-22)**: Fixed in commit `a95b677` (`Fix linter and format issues in the tests`). `music_ferry/notify.py` now catches `requests.RequestException` and logs `logger.warning("Notification failed: %s", exc)`.

---

### 9. `youtube/downloader.py:174` — Wrong type annotation

```python
def download_tracks(self, tracks: list[Track], on_progress: callable = None):
```

`callable` is not a valid type annotation. Should be:
```python
from collections.abc import Callable
on_progress: Callable[[int, int, Track], None] | None = None
```

**Status (verified 2026-03-22)**: Fixed in commit `a95b677` (`Fix linter and format issues in the tests`). `music_ferry/youtube/downloader.py` now imports `Callable` and uses `Callable[[int, int, Track], None] | None`.

---

### 10. `transfer.py:98` — Untyped `config` parameter

```python
def __init__(self, config, sources: list[str] | None = None, ...):
```

Should be `config: Config`. mypy strict mode likely catches this but it's a readability issue.

**Status (verified 2026-03-22)**: Fixed in commit `a95b677` (`Fix linter and format issues in the tests`). `InteractiveTransfer.__init__()` now annotates `config: Config`.

---

### 11. `browser.py` — `Optional[X]` instead of `X | None`

```python
from typing import Optional
self._browser: Optional[Browser] = None
```

Inconsistent with the rest of the codebase (which uses `X | None`). Also imports `re` and `time` inside methods instead of at module top.

**Status (verified 2026-03-22)**: Fixed in commit `713b3e9` (`fix(browser): move regex and time imports to module scope`). The earlier type cleanup from `a95b677` is now complete; `browser.py` uses `X | None` annotations and keeps `re`/`time` at module scope.

---

### 12. `config.py:16-27` — Lazy validation of playlist URLs

`PlaylistConfig.playlist_id` raises `ValueError` if the URL is malformed, but this is only triggered when the property is accessed (mid-sync), not at `load_config()` time. A bad URL in config causes a confusing mid-run crash.

The URL → ID extraction should happen eagerly in `load_config()` and stored as a field, or `playlist_id` should be validated as part of config loading.

**Status (verified 2026-03-22)**: Fixed in commit `d566206` (`fix(config): validate playlist urls during load`). `load_config()` now validates every parsed playlist URL immediately and raises a source-specific `ValueError` before sync starts.

---

### 13. `sync_service.py:423-431` — Module-level global singleton dict

```python
_sync_services: dict[int, SyncService] = {}

def get_sync_service(app: FastAPI) -> SyncService:
    app_id = id(app)
    if app_id not in _sync_services:
        _sync_services[app_id] = SyncService(app)
    return _sync_services[app_id]
```

`id(app)` can be reused after garbage collection. This dict leaks across the process lifetime and complicates test isolation (tests creating new `FastAPI()` instances may get stale services if the old app object is GC'd and a new one happens to get the same `id`).

Prefer storing the service on `app.state` at startup in the lifespan handler.

**Status (verified 2026-03-22)**: Not fixed. `music_ferry/web/services/sync_service.py` still uses the module-level `_sync_services: dict[int, SyncService] = {}` cache keyed by `id(app)`.

---

## Architecture Observations

### Library has no concurrency protection
`Library` is a plain in-memory dict + JSON file with no locking. The web UI's `LibraryService` reads the library while `SyncService` may be writing it from a worker thread. Currently safe because each sync creates a fresh `Orchestrator` (and fresh `Library`), and only one sync runs at a time (enforced by `_lock`). But this is a fragile invariant — document it or add a file lock.

### `Track` dataclass is shared between Spotify and YouTube
`spotify_api.Track` is reused for YouTube tracks (with `source="youtube"`). The `album_art_url` field is Spotify-specific and `duration_ms` semantics differ slightly. This is workable but could cause confusion when adding a third source. Consider a `BaseTrack` protocol or a union type if a third source is ever added.

### Config loading is verbose but correct
`load_config()` manually maps YAML keys to dataclasses. This is readable and avoids hidden magic, but adding new config fields requires changes in 3 places (dataclass, load_config, config.yaml example). Consider documenting this pattern explicitly in `coding-conventions.md`.

---

## Summary

| Severity | Count |
|---|---|
| Critical | 4 |
| Medium | 3 |
| Code quality | 6 |

Recommended fix order:
1. `tagger.py` ID3 bug (causes silent data loss)
2. `cli.py` source flags bug (documented feature doesn't work)
3. `library.py` atomic writes (data integrity)
4. `orchestrator.py` empty playlist_id (library pollution)
5. `recorder.py` silent sink failure + TimeoutExpired
