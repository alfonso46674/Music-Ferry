# Music Ferry — Coding Conventions

Patterns, anti-patterns, and conventions for this codebase.

---

## Language and Style

### Always
- Python 3.11+ syntax: `X | None` (not `Optional[X]`), `list[X]` (not `List[X]`), `dict[K, V]`
- `@dataclass` for data containers; prefer `field(default_factory=...)` for mutable defaults
- `logging.getLogger(__name__)` per module — no `print()` in library code
- Type annotations on all function signatures (mypy strict mode is enforced)
- Line length 88 (black/ruff)

### Never
- `Optional[X]` from `typing` — use `X | None`
- `List`, `Dict`, `Tuple` from `typing` — use lowercase built-ins
- `from typing import ...` for things available as built-in generics in 3.11

---

## Error Handling

### Always
```python
# Log before swallowing
except requests.RequestException as exc:
    logger.warning("Notification failed: %s", exc)
    return

# Catch specific exceptions, not bare except
except (OSError, json.JSONDecodeError) as exc:
    logger.warning("Failed to read %s: %s", path, exc)
```

### Never
```python
except Exception:
    pass  # Silent swallowing - always at minimum log the failure

except:    # bare except - never
    pass
```

### Subprocess calls
Always check returncode:
```python
result = subprocess.run([...], capture_output=True, text=True)
if result.returncode != 0:
    raise RuntimeError(f"Command failed: {result.stderr}")
```

Always handle `TimeoutExpired` when using `wait(timeout=...)`:
```python
try:
    process.wait(timeout=5)
except subprocess.TimeoutExpired:
    process.kill()
    process.wait()
```

---

## File Persistence (Library)

### Atomic writes
The library JSON is critical state. Always write atomically:
```python
import tempfile

def save(self) -> None:
    tmp = self.db_path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(self.db_path)  # atomic on POSIX
```

Never write directly to the destination file — a crash mid-write corrupts it.

### No empty playlist IDs
When adding a track to the library before its playlist is known, do not pass `""`:
```python
# Wrong — pollutes playlists list with ""
library.add_track(track.id, filename, title, artist, "")

# Correct — use a sentinel or defer playlist association
library.add_track(track.id, filename, title, artist, playlist_id)
# Let _update_playlist_membership() handle membership after download
```

---

## Config and Typing

### Type the `config` parameter explicitly
```python
# Wrong
def __init__(self, config, ...):

# Correct
from music_ferry.config import Config
def __init__(self, config: Config, ...):
```

### Validate eagerly in `load_config()`
Bad URLs or missing fields should fail at load time, not when a property is first accessed:
```python
# Wrong — lazy validation, fails mid-sync
@property
def playlist_id(self) -> str:
    match = re.search(r"playlist/([a-zA-Z0-9]+)", self.url)
    if match:
        return match.group(1)
    raise ValueError(...)  # surprise failure later

# Correct — validate and extract ID at load time
```

---

## Source Flags (`--spotify` / `--youtube`)

The CLI's `--spotify` and `--youtube` flags must be resolved via `_resolve_sources()` and passed to both sync and transfer operations. Never ignore these flags.

```python
# Correct pattern in main()
sync_spotify, sync_youtube = _resolve_sources(args, config)
result = asyncio.run(orchestrator.run(sync_spotify=sync_spotify, sync_youtube=sync_youtube))
```

---

## Async Patterns

### Web UI (FastAPI)
- Keep route handlers thin: parse request, call service, return response
- Blocking I/O in routes → run in executor: `await loop.run_in_executor(None, blocking_fn, args...)`
- Long-running sync → `asyncio.to_thread()` (used in `sync_service.py`)
- Never call `asyncio.run()` on the web event loop — only in worker threads

### Background tasks
```python
# Correct — fire and forget from async context
asyncio.create_task(self._run_sync(job, ...))

# Wrong in an async context
asyncio.run(...)  # creates new event loop, crashes if one is already running
```

---

## Singleton / App State

Avoid module-level global dicts for per-app state. Prefer `app.state`:
```python
# Avoid
_services: dict[int, Service] = {}
def get_service(app): ...

# Prefer — store directly on app.state at startup
app.state.sync_service = SyncService(app)
```

If a module-level cache is used, document why and ensure it handles test isolation.

---

## Subprocess (Recorder / Transfer)

### Creating virtual audio sinks
Always verify sink creation succeeded before proceeding:
```python
result = subprocess.run(["pactl", "load-module", ...], capture_output=True, text=True)
if result.returncode != 0:
    raise RuntimeError(f"Failed to create virtual sink: {result.stderr}")
self._module_id = int(result.stdout.strip())
```

### File transfer
Prefer `shutil.copy2()` for individual files (preserves metadata). For bulk transfers, `rsync` via subprocess is acceptable.

---

## Logging

```python
logger = logging.getLogger(__name__)  # one per module, at top level

# Use %s formatting (not f-strings) for logger calls — lazy evaluation
logger.info("Syncing playlist %s: %d new tracks", playlist.name, len(new_tracks))

# f-strings are fine for exception messages, runtime strings
raise RuntimeError(f"Mount not found: {mount}")
```

---

## Adding a New Source (Beyond Spotify/YouTube)

1. Add config dataclass in `config.py` and parse it in `load_config()`
2. Create a `music_ferry/<source>/` package with a `downloader.py`
3. Add a `_sync_<source>()` method in `orchestrator.py`
4. Wire up `--<source>` flag in `cli.py` via `_add_source_flags()` + `_resolve_sources()`
5. Add corresponding library path (`config.paths.music_dir / "<source>"`)
6. Update `web/services/library_service.py` to expose the new source
7. Add tests in `tests/test_<source>_downloader.py`

---

## Adding a New Web API Endpoint

1. Define a Pydantic model for any request body in `web/routes/api.py`
2. Add handler in the appropriate `web/routes/*.py` file — keep it to: parse → call service → return
3. Business logic goes in `web/services/` not in the route
4. Return `{"error": "..."}` for expected failures; raise `HTTPException` only for truly unexpected ones
5. Add tests in `tests/test_web_api.py` using the HTTPX test client

---

## What Not to Do

| Anti-Pattern | Correct Approach |
|---|---|
| `Optional[X]` from typing | `X \| None` |
| `except Exception: pass` | Catch specific, log the error |
| Writing directly to `library.json` | Write to `.tmp`, then `replace()` |
| `library.add_track(..., "")` | Always pass real playlist_id |
| Untyped `config` parameter | `config: Config` |
| `callable` as type hint | `Callable[[...], ...]` from `collections.abc` |
| `asyncio.run()` inside async context | `asyncio.create_task()` or `asyncio.to_thread()` |
| Ignoring subprocess returncode | Always check and raise on failure |
| Module-level global singletons | `app.state` or passed explicitly |
| Lazy config validation (property raises) | Validate eagerly in `load_config()` |
