# spotify_swimmer/browser.py
import asyncio
import json
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page, BrowserContext


class SpotifyBrowser:
    def __init__(self, cookies_dir: Path, audio_sink: str):
        self.cookies_dir = cookies_dir
        self.audio_sink = audio_sink
        self.base_url = "https://open.spotify.com"
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        await self._launch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close()

    async def _launch(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                f"--audio-output-device={self.audio_sink}",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )
        self._context = await self._browser.new_context()

        # Load cookies if they exist
        cookies_file = self.cookies_dir / "spotify-session.json"
        if cookies_file.exists():
            cookies = json.loads(cookies_file.read_text())
            await self._context.add_cookies(cookies)

        self.page = await self._context.new_page()

    async def _close(self) -> None:
        if self._context:
            # Save cookies for next session
            cookies = await self._context.cookies()
            self.cookies_dir.mkdir(parents=True, exist_ok=True)
            cookies_file = self.cookies_dir / "spotify-session.json"
            cookies_file.write_text(json.dumps(cookies))

        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def _get_playlist_url(self, playlist_id: str) -> str:
        return f"{self.base_url}/playlist/{playlist_id}"

    def _get_track_url(self, track_id: str) -> str:
        return f"{self.base_url}/track/{track_id}"

    async def navigate_to_playlist(self, playlist_id: str) -> None:
        url = self._get_playlist_url(playlist_id)
        await self.page.goto(url, wait_until="networkidle")

    async def play_track(self, track_id: str) -> None:
        url = self._get_track_url(track_id)
        await self.page.goto(url, wait_until="networkidle")

        play_button = self.page.locator('[data-testid="play-button"]')
        await play_button.wait_for(state="visible", timeout=10000)
        await play_button.click()

    async def pause(self) -> None:
        pause_button = self.page.locator('[data-testid="control-button-pause"]')
        if await pause_button.is_visible():
            await pause_button.click()

    async def is_logged_in(self) -> bool:
        await self.page.goto(self.base_url, wait_until="networkidle")
        login_button = self.page.locator('[data-testid="login-button"]')
        return not await login_button.is_visible()
