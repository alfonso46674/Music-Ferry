# spotify_swimmer/notify.py
from dataclasses import dataclass, field

import requests


@dataclass
class PlaylistResult:
    name: str
    tracks_synced: int
    error: str | None


@dataclass
class SyncResult:
    playlists: list[PlaylistResult]
    transferred: bool
    global_error: str | None = None

    @property
    def total_tracks(self) -> int:
        return sum(p.tracks_synced for p in self.playlists)

    @property
    def has_errors(self) -> bool:
        return any(p.error is not None for p in self.playlists)

    @property
    def is_success(self) -> bool:
        return not self.has_errors and self.global_error is None and self.total_tracks > 0

    @property
    def is_failure(self) -> bool:
        return self.global_error is not None or self.total_tracks == 0


class Notifier:
    def __init__(
        self,
        ntfy_server: str,
        ntfy_topic: str,
        notify_on_success: bool,
        notify_on_failure: bool,
    ):
        self.ntfy_server = ntfy_server.rstrip("/")
        self.ntfy_topic = ntfy_topic
        self.notify_on_success = notify_on_success
        self.notify_on_failure = notify_on_failure

    def send(self, result: SyncResult) -> None:
        if result.is_success and not self.notify_on_success:
            return
        if not result.is_success and not self.notify_on_failure:
            return

        title, body = self._format_message(result)
        self._send_notification(title, body)

    def _format_message(self, result: SyncResult) -> tuple[str, str]:
        if result.is_failure:
            title = "❌ Spotify Swimmer Failed"
            body = f"{result.global_error or 'Sync failed'}\n\nPlaylists:\n"
            for p in result.playlists:
                body += f"• {p.name}: Not synced\n"
        elif result.has_errors:
            title = "⚠️ Spotify Swimmer Partial"
            body = f"Synced {result.total_tracks} new tracks. Some issues occurred.\n\nPlaylists:\n"
            for p in result.playlists:
                if p.error:
                    body += f"• {p.name}: Failed ({p.error})\n"
                else:
                    body += f"• {p.name}: {p.tracks_synced} new tracks\n"
            if result.transferred:
                body += "\nTransferred to headphones."
        else:
            title = "🏊 Spotify Swimmer Complete"
            body = f"Synced {result.total_tracks} new tracks."
            if result.transferred:
                body += " Transferred to headphones."
            body += "\n\nPlaylists:\n"
            for p in result.playlists:
                body += f"• {p.name}: {p.tracks_synced} new tracks\n"

        return title, body

    def _send_notification(self, title: str, body: str) -> None:
        url = f"{self.ntfy_server}/{self.ntfy_topic}"
        requests.post(
            url,
            data=body,
            headers={"Title": title},
        )
