# music_ferry/web/services/log_service.py
"""Service for tailing log files and streaming to clients."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from music_ferry.config import Config

logger = logging.getLogger(__name__)


class LogService:
    """Service for tailing and streaming log files."""

    def __init__(self, config: Config):
        self.config = config
        self._log_buffer: list[str] = []
        self._max_buffer = 100

    def _get_log_path(self) -> Path | None:
        """Get the path to the log file if it exists."""
        # Check common log locations
        log_dir = self.config.paths.music_dir / "logs"
        if log_dir.exists():
            log_files = sorted(
                log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            if log_files:
                return log_files[0]
        return None

    async def tail_logs(
        self,
        lines: int = 50,
        follow: bool = True,
    ) -> AsyncGenerator[str, None]:
        """Tail log file and yield new lines.

        Args:
            lines: Number of initial lines to return.
            follow: Whether to continue following the file.

        Yields:
            Log lines as strings.
        """
        log_path = self._get_log_path()

        if log_path is None:
            # No log file yet - yield a message and wait for logs
            yield "[INFO] No log file found. Waiting for new logs..."

            while follow:
                await asyncio.sleep(1)
                log_path = self._get_log_path()
                if log_path:
                    break

            if not log_path:
                return

        # Read initial lines
        try:
            with open(log_path) as f:
                all_lines = f.readlines()
                initial = all_lines[-lines:] if len(all_lines) > lines else all_lines

                for line in initial:
                    yield line.rstrip("\n")

                if not follow:
                    return

                # Follow the file
                while True:
                    current_pos = f.tell()
                    line = f.readline()

                    if line:
                        yield line.rstrip("\n")
                    else:
                        # Check if file was rotated
                        try:
                            if log_path.stat().st_size < current_pos:
                                # File was truncated/rotated, seek to beginning
                                f.seek(0)
                        except FileNotFoundError:
                            # File was deleted, check for new file
                            new_path = self._get_log_path()
                            if new_path and new_path != log_path:
                                log_path = new_path
                                break  # Exit inner loop to reopen file

                        await asyncio.sleep(0.5)

        except FileNotFoundError:
            yield f"[ERROR] Log file not found: {log_path}"
        except PermissionError:
            yield f"[ERROR] Permission denied: {log_path}"
        except Exception as e:
            yield f"[ERROR] Failed to read log file: {e}"


class InMemoryLogHandler(logging.Handler):
    """Log handler that stores logs in memory for streaming."""

    _instances: list["InMemoryLogHandler"] = []

    def __init__(self, max_lines: int = 1000):
        super().__init__()
        self.max_lines = max_lines
        self._buffer: list[str] = []
        self._lock = asyncio.Lock()
        self._new_log_event = asyncio.Event()
        InMemoryLogHandler._instances.append(self)

    def emit(self, record: logging.LogRecord) -> None:
        """Handle a log record."""
        try:
            msg = self.format(record)
            # Use thread-safe append
            self._buffer.append(msg)
            if len(self._buffer) > self.max_lines:
                self._buffer = self._buffer[-self.max_lines :]

            # Signal new log available
            self._new_log_event.set()
        except Exception:
            self.handleError(record)

    async def get_lines(self, start: int = 0) -> list[str]:
        """Get log lines starting from index."""
        return self._buffer[start:]

    async def wait_for_new_log(self, timeout: float = 30.0) -> bool:
        """Wait for a new log entry."""
        try:
            await asyncio.wait_for(self._new_log_event.wait(), timeout)
            self._new_log_event.clear()
            return True
        except TimeoutError:
            return False

    @classmethod
    def get_handler(cls) -> "InMemoryLogHandler | None":
        """Get the first registered handler."""
        return cls._instances[0] if cls._instances else None
