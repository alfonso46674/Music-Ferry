# tests/test_notify.py
from unittest.mock import MagicMock, patch

from music_ferry.notify import Notifier, PlaylistResult, SyncResult


class TestNotifier:
    def test_sync_result_total_tracks(self):
        result = SyncResult(
            playlists=[
                PlaylistResult(name="Playlist 1", tracks_synced=5, error=None),
                PlaylistResult(name="Playlist 2", tracks_synced=3, error=None),
            ],
            transferred=True,
        )
        assert result.total_tracks == 8
        assert result.has_errors is False
        assert result.is_success is True

    def test_sync_result_with_errors(self):
        result = SyncResult(
            playlists=[
                PlaylistResult(name="Playlist 1", tracks_synced=5, error=None),
                PlaylistResult(name="Playlist 2", tracks_synced=0, error="Not found"),
            ],
            transferred=True,
        )
        assert result.total_tracks == 5
        assert result.has_errors is True
        assert result.is_success is False

    def test_sync_result_all_failed(self):
        result = SyncResult(
            playlists=[
                PlaylistResult(
                    name="Playlist 1", tracks_synced=0, error="Login expired"
                ),
            ],
            transferred=False,
            global_error="Login expired",
        )
        assert result.is_failure is True

    @patch("music_ferry.notify.requests.post")
    def test_send_success_notification(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)

        notifier = Notifier(
            ntfy_server="https://ntfy.sh",
            ntfy_topic="test-topic",
            notify_on_success=True,
            notify_on_failure=True,
        )

        result = SyncResult(
            playlists=[
                PlaylistResult(name="Discover Weekly", tracks_synced=8, error=None),
                PlaylistResult(name="Workout Mix", tracks_synced=4, error=None),
            ],
            transferred=True,
        )

        notifier.send(result)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "ntfy.sh/test-topic" in call_args[0][0]
        assert "Music Ferry Complete" in call_args[1]["headers"]["Title"]
        body = call_args[1]["data"].decode("utf-8")
        assert "12 new tracks" in body
        assert "Discover Weekly: 8 new tracks" in body
        assert "Workout Mix: 4 new tracks" in body

    @patch("music_ferry.notify.requests.post")
    def test_send_failure_notification(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)

        notifier = Notifier(
            ntfy_server="https://ntfy.sh",
            ntfy_topic="test-topic",
            notify_on_success=True,
            notify_on_failure=True,
        )

        result = SyncResult(
            playlists=[
                PlaylistResult(name="Discover Weekly", tracks_synced=0, error=None),
            ],
            transferred=False,
            global_error="Login expired",
        )

        notifier.send(result)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "Music Ferry Failed" in call_args[1]["headers"]["Title"]
        body = call_args[1]["data"].decode("utf-8")
        assert "Login expired" in body

    @patch("music_ferry.notify.requests.post")
    def test_skip_success_notification_when_disabled(self, mock_post):
        notifier = Notifier(
            ntfy_server="https://ntfy.sh",
            ntfy_topic="test-topic",
            notify_on_success=False,
            notify_on_failure=True,
        )

        result = SyncResult(
            playlists=[
                PlaylistResult(name="Discover Weekly", tracks_synced=8, error=None),
            ],
            transferred=True,
        )

        notifier.send(result)
        mock_post.assert_not_called()
