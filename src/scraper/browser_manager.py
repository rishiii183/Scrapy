"""
Browser Lifecycle Manager with Anti-Bot Flags for Google Maps Scraping.

Orchestrates Playwright Chromium / Google Chrome with:
- '--disable-blink-features=AutomationControlled'
- Realistic user-agent and viewport configuration
- Graceful context teardown preventing orphaned browser processes
"""

import logging
from typing import List, Optional
from playwright.sync_api import (
    sync_playwright,
    Playwright,
    Browser,
    BrowserContext,
    Page,
)

from src.config import (
    get_chrome_executable,
    DEFAULT_BROWSER_ARGS,
    DEFAULT_USER_AGENT,
    DEFAULT_VIEWPORT,
)

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Manages Playwright browser lifecycle with anti-bot safeguards.
    Supports both context manager syntax and manual start/stop.
    """

    def __init__(
        self,
        headless: bool = True,
        executable_path: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
        user_agent: Optional[str] = None,
        viewport: Optional[dict] = None,
    ):
        self.headless = headless
        self.executable_path = executable_path or get_chrome_executable()
        self.args = list(DEFAULT_BROWSER_ARGS)
        if extra_args:
            self.args.extend(extra_args)
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.viewport = viewport or DEFAULT_VIEWPORT

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    def start(self) -> BrowserContext:
        """
        Initialize Playwright and launch the browser with configured anti-bot options.
        Returns the active BrowserContext.
        """
        if self._context is not None:
            return self._context

        self._playwright = sync_playwright().start()

        launch_kwargs = {
            "headless": self.headless,
            "args": self.args,
        }

        if self.executable_path:
            launch_kwargs["executable_path"] = self.executable_path
            logger.info("Launching Chrome from: %s", self.executable_path)
        else:
            logger.info("Chrome executable not found on disk; falling back to bundled Chromium.")

        try:
            self._browser = self._playwright.chromium.launch(**launch_kwargs)
        except Exception as exc:
            # If specified executable failed, try default chromium launch
            if self.executable_path:
                logger.warning("Failed launching with executable_path '%s': %s. Retrying bundled chromium...", self.executable_path, exc)
                launch_kwargs.pop("executable_path", None)
                self._browser = self._playwright.chromium.launch(**launch_kwargs)
            else:
                raise

        self._context = self._browser.new_context(
            user_agent=self.user_agent,
            viewport=self.viewport,
            locale="en-US",
            timezone_id="America/Chicago",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        return self._context

    def new_page(self) -> Page:
        """Create a new page within the active browser context."""
        context = self.start()
        return context.new_page()

    def close(self) -> None:
        """Safely close context, browser, and playwright runner."""
        if self._context:
            try:
                self._context.close()
            except Exception as e:
                logger.debug("Error closing context: %s", e)
            self._context = None

        if self._browser:
            try:
                self._browser.close()
            except Exception as e:
                logger.debug("Error closing browser: %s", e)
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception as e:
                logger.debug("Error stopping playwright: %s", e)
            self._playwright = None

    def __enter__(self) -> "BrowserManager":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
