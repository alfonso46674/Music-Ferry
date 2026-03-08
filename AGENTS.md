# Music Ferry — AGENTS.md

Guidance for AI agents working in this repository.

## Quick Context

- **Language**: Python 3.11, strict mypy, ruff + black formatting
- **Test runner**: `pytest` (asyncio_mode = auto); run `make test`
- **Lint/type**: `make lint` (ruff) and `make typecheck` (mypy --strict)
- **Deployment**: Docker Compose (`docker compose --env-file .env.docker up -d --build`)
- See [`CLAUDE.md`](CLAUDE.md) for architecture and key paths

## Before Touching Code

1. Read the file(s) you plan to change — don't guess at implementation
2. Run `make check` (lint + typecheck + test) to confirm the baseline is clean
3. Check [`docs/plans/2026-03-07-code-audit.md`](docs/plans/2026-03-07-code-audit.md) for known bugs before adding workarounds

## Coding Rules

See [`coding-conventions.md`](coding-conventions.md) for full conventions. Key rules:

- **No bare `except:`** — always catch specific exceptions and log failures
- **Atomic file writes** — use a temp file + `replace()` for `library.json` saves
- **Typed `config` parameters** — always use `Config` (not bare `config`)
- **`X | None` syntax** — no `Optional[X]` from `typing` (use PEP 604 union)
- **Log don't swallow** — silent failure is not acceptable; at minimum `logger.warning()`
- **Verify subprocess success** — always check returncode after `subprocess.run()`

## Testing Guidelines

- Tests live in `tests/`; fixtures in `tests/fixtures/`
- Use `pytest-asyncio` for async tests — no manual `asyncio.run()` in tests
- Mock filesystem/subprocess/network in unit tests; `tests/test_integration.py` is the only integration test
- Match existing test style (see `tests/test_orchestrator.py` for orchestrator patterns)

## Boundaries

- **`library.py`** is the single source of truth for track/playlist state — all persistence goes through it
- **`orchestrator.py`** orchestrates Spotify recording; never add download logic directly there
- **`web/services/`** contains all FastAPI business logic — keep routes thin (request parsing only)
- **`config.py`** loading is eager — validate everything in `load_config()`, not at property access time

## Common Pitfalls

- Adding `playlist_id=""` to `library.add_track()` — always use the real ID or skip playlist association
- Forgetting `--spotify`/`--youtube` flags must flow through `_resolve_sources()` into `orchestrator.run()`
- Not handling `subprocess.TimeoutExpired` after calling `process.wait(timeout=...)`
- Using module-level global dicts for per-request/per-app state (use `app.state` or pass explicitly)
