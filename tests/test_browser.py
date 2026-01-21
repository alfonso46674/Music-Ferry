# tests/test_browser.py
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from spotify_swimmer.browser import SpotifyBrowser


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
    @patch("spotify_swimmer.browser.async_playwright")
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
    @patch("spotify_swimmer.browser.async_playwright")
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
