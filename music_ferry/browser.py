# music_ferry/browser.py
import asyncio
import json
import random
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, Page, BrowserContext


# Common desktop user agents (Chrome on Linux)
USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

# Common screen resolutions
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
]

# JavaScript to mask automation detection
STEALTH_JS = """
() => {
    // Override navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });

    // Override navigator.plugins to look real
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' }
        ]
    });

    // Override navigator.languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en']
    });

    // Override chrome runtime
    window.chrome = {
        runtime: {}
    };

    // Override permissions query
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
}
"""


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

        # Select random user agent and viewport for this session
        user_agent = random.choice(USER_AGENTS)
        viewport = random.choice(VIEWPORTS)

        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                f"--audio-output-device={self.audio_sink}",
                "--autoplay-policy=no-user-gesture-required",
                # Stealth args to hide automation
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-sync",
                "--disable-translate",
                "--hide-scrollbars",
                "--metrics-recording-only",
                "--mute-audio=false",
            ],
        )

        self._context = await self._browser.new_context(
            user_agent=user_agent,
            viewport=viewport,
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Inject stealth script before any page loads
        await self._context.add_init_script(STEALTH_JS)

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

    async def _random_delay(self, min_ms: int = 500, max_ms: int = 2000) -> None:
        """Add a random delay to mimic human behavior."""
        delay = random.uniform(min_ms / 1000, max_ms / 1000)
        await asyncio.sleep(delay)

    async def navigate_to_playlist(self, playlist_id: str) -> None:
        url = self._get_playlist_url(playlist_id)
        await self.page.goto(url, wait_until="networkidle")
        await self._random_delay(1000, 3000)

    async def play_track(self, track_id: str) -> None:
        url = self._get_track_url(track_id)
        await self.page.goto(url, wait_until="networkidle")

        # Random delay before clicking play (like a human looking at the page)
        await self._random_delay(800, 2500)

        play_button = self.page.locator('[data-testid="play-button"]')
        await play_button.wait_for(state="visible", timeout=10000)
        await play_button.click()

    async def pause(self) -> None:
        await self._random_delay(300, 800)
        pause_button = self.page.locator('[data-testid="control-button-pause"]')
        if await pause_button.is_visible():
            await pause_button.click()

    async def is_logged_in(self) -> bool:
        await self.page.goto(self.base_url, wait_until="networkidle")
        await self._random_delay(500, 1500)
        login_button = self.page.locator('[data-testid="login-button"]')
        return not await login_button.is_visible()

    async def play_playlist(self, playlist_id: str) -> None:
        """Navigate to playlist and start playing from the first track."""
        url = self._get_playlist_url(playlist_id)
        await self.page.goto(url, wait_until="networkidle")

        # Random delay before clicking play (like a human looking at the page)
        await self._random_delay(1000, 3000)

        play_button = self.page.locator('[data-testid="play-button"]')
        await play_button.wait_for(state="visible", timeout=10000)
        await play_button.click()

    async def skip_to_next(self) -> None:
        """Skip to the next track in the current playback."""
        await self._random_delay(300, 800)
        skip_button = self.page.locator('[data-testid="control-button-skip-forward"]')
        await skip_button.wait_for(state="visible", timeout=5000)
        await skip_button.click()

    def get_current_track_id(self) -> Optional[str]:
        """Extract the track ID from the current page URL.

        Returns None if not on a track page.
        """
        import re

        url = self.page.url
        match = re.search(r"/track/([a-zA-Z0-9]+)", url)
        if match:
            return match.group(1)
        return None

    async def wait_for_track_change(
        self,
        current_track_id: str,
        timeout_seconds: float = 300,
    ) -> Optional[str]:
        """Wait for the track to change from the current one.

        Returns the new track ID or None if timeout reached.
        """
        import time

        start_time = time.time()
        poll_interval = 1.0  # Check every second

        while time.time() - start_time < timeout_seconds:
            new_track_id = self.get_current_track_id()
            if new_track_id and new_track_id != current_track_id:
                return new_track_id
            await asyncio.sleep(poll_interval)

        return None
