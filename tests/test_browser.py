# tests/test_browser.py
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from music_ferry.browser import SpotifyBrowser


class TestSpotifyBrowser:
    def test_playlist_url_construction(self):
        browser = SpotifyBrowser.__new__(SpotifyBrowser)
        browser.base_url = "https://open.spotify.com"

        url = browser._get_playlist_url("abc123")
        assert url == "https://open.spotify.com/playlist/abc123"

    def test_track_url_construction(self):
        browser = SpotifyBrowser.__new__(SpotifyBrowser)
        browser.base_url = "https://open.spotify.com"

        url = browser._get_track_url("xyz789")
        assert url == "https://open.spotify.com/track/xyz789"


class TestSpotifyBrowserIntegration:
    @pytest.mark.asyncio
    @patch("music_ferry.browser.async_playwright")
    async def test_launch_and_close(self, mock_playwright):
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        # Mock the async_playwright().start() pattern - start() is async
        mock_pw_manager = MagicMock()
        mock_pw_manager.start = AsyncMock(return_value=mock_pw)
        mock_playwright.return_value = mock_pw_manager
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        # cookies() returns a list for JSON serialization
        mock_context.cookies = AsyncMock(return_value=[])

        async with SpotifyBrowser(
            cookies_dir=Path("/tmp/cookies"),
            audio_sink="test-sink",
        ) as browser:
            assert browser.page is mock_page

        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    @patch("music_ferry.browser.async_playwright")
    async def test_play_track(self, mock_playwright):
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        # Mock the async_playwright().start() pattern - start() is async
        mock_pw_manager = MagicMock()
        mock_pw_manager.start = AsyncMock(return_value=mock_pw)
        mock_playwright.return_value = mock_pw_manager
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        # cookies() returns a list for JSON serialization
        mock_context.cookies = AsyncMock(return_value=[])

        # Mock the locator to return a mock with wait_for and click methods
        mock_locator = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_locator)

        async with SpotifyBrowser(
            cookies_dir=Path("/tmp/cookies"),
            audio_sink="test-sink",
        ) as browser:
            await browser.play_track("track123")

        mock_page.goto.assert_called()
        mock_locator.click.assert_called()

    @pytest.mark.asyncio
    @patch("music_ferry.browser.async_playwright")
    async def test_play_playlist(self, mock_playwright):
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw_manager = MagicMock()
        mock_pw_manager.start = AsyncMock(return_value=mock_pw)
        mock_playwright.return_value = mock_pw_manager
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.cookies = AsyncMock(return_value=[])

        mock_locator = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_locator)

        async with SpotifyBrowser(
            cookies_dir=Path("/tmp/cookies"),
            audio_sink="test-sink",
        ) as browser:
            await browser.play_playlist("playlist123")

        # Should navigate to playlist URL
        call_args = mock_page.goto.call_args_list[-1]
        assert "playlist/playlist123" in call_args[0][0]
        # Should click play button
        mock_locator.click.assert_called()

    @pytest.mark.asyncio
    @patch("music_ferry.browser.async_playwright")
    async def test_skip_to_next(self, mock_playwright):
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw_manager = MagicMock()
        mock_pw_manager.start = AsyncMock(return_value=mock_pw)
        mock_playwright.return_value = mock_pw_manager
        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.cookies = AsyncMock(return_value=[])

        mock_locator = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_locator)

        async with SpotifyBrowser(
            cookies_dir=Path("/tmp/cookies"),
            audio_sink="test-sink",
        ) as browser:
            await browser.skip_to_next()

        # Should click the skip forward button
        mock_page.locator.assert_called_with(
            '[data-testid="control-button-skip-forward"]'
        )
        mock_locator.click.assert_called()


class TestBrowserUrlParsing:
    def test_get_current_track_id_from_track_url(self):
        browser = SpotifyBrowser.__new__(SpotifyBrowser)
        browser.base_url = "https://open.spotify.com"
        browser.page = MagicMock()
        browser.page.url = "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh"

        track_id = browser.get_current_track_id()
        assert track_id == "4iV5W9uYEdYUVa79Axb7Rh"

    def test_get_current_track_id_with_query_params(self):
        browser = SpotifyBrowser.__new__(SpotifyBrowser)
        browser.base_url = "https://open.spotify.com"
        browser.page = MagicMock()
        browser.page.url = (
            "https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh?si=abc123"
        )

        track_id = browser.get_current_track_id()
        assert track_id == "4iV5W9uYEdYUVa79Axb7Rh"

    def test_get_current_track_id_returns_none_for_non_track(self):
        browser = SpotifyBrowser.__new__(SpotifyBrowser)
        browser.base_url = "https://open.spotify.com"
        browser.page = MagicMock()
        browser.page.url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"

        track_id = browser.get_current_track_id()
        assert track_id is None


class TestWaitForTrackChange:
    @pytest.mark.asyncio
    async def test_wait_for_track_change_detects_change(self):
        browser = SpotifyBrowser.__new__(SpotifyBrowser)
        browser.page = MagicMock()

        # URL changes after 2 checks
        browser.page.url = "https://open.spotify.com/track/track1"

        async def mock_sleep(duration):
            browser.page.url = "https://open.spotify.com/track/track2"

        with patch("music_ferry.browser.asyncio.sleep", side_effect=mock_sleep):
            new_track = await browser.wait_for_track_change(
                "track1", timeout_seconds=10
            )

        assert new_track == "track2"

    @pytest.mark.asyncio
    async def test_wait_for_track_change_times_out(self):
        browser = SpotifyBrowser.__new__(SpotifyBrowser)
        browser.page = MagicMock()
        browser.page.url = "https://open.spotify.com/track/track1"

        with patch("music_ferry.browser.asyncio.sleep", new_callable=AsyncMock):
            new_track = await browser.wait_for_track_change(
                "track1", timeout_seconds=0.1
            )

        assert new_track is None
