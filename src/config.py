"""
Global Configuration and System Settings for Roofer Outreach Pipeline.

Defines:
- Filesystem paths and directory structure
- Chrome executable path resolution with anti-bot configuration
- Scraping defaults, target states, and scroll settings
- Pacing limits and Google Sheet CRM configurations
"""

import os
from pathlib import Path
from typing import List, Optional

# Filesystem Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"

# Browser & Anti-Bot Configuration
DEFAULT_CHROME_PATH = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
FALLBACK_EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
FALLBACK_SYSTEM_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

DEFAULT_BROWSER_ARGS: List[str] = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--disable-background-timer-throttling",
    "--disable-popup-blocking",
    "--lang=en-US,en",
]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_VIEWPORT = {"width": 1280, "height": 900}

# Scraping Engine Settings
MAPS_BASE_URL = "https://www.google.com/maps/search/"
DEFAULT_SCROLL_COUNT = 4
SCROLL_PAUSE_SECONDS = 1.5
PAGE_LOAD_TIMEOUT_MS = 30000
FEED_WAIT_TIMEOUT_MS = 10000

# Geographic Targets
TARGET_STATES = ["TX", "FL", "OH", "GA", "AZ"]

# Priority Scoring Thresholds
HIGH_PRIORITY_REVIEW_THRESHOLD = 10

# Humanized Outreach Pacing and Limits
MIN_DELAY_SECONDS = 45
MAX_DELAY_SECONDS = 180
DAILY_SEND_CAP = 25

# Google Sheet CRM Target
SHEET_ID = "12WdL1U83byQW7tTbu0eY9oSZrGz212HN4Rzlhq6BitY"
SHEET_TAB = "Leads Tracker"
START_ROW = 14


def get_chrome_executable() -> Optional[str]:
    """
    Resolve Chrome or Chromium executable path.
    Prioritizes:
    1. Environment variable CHROME_PATH
    2. %LOCALAPPDATA%\\Google\\Chrome\\Application\\chrome.exe
    3. Standard Program Files Chrome paths
    4. Microsoft Edge fallback
    Returns the first path that exists on disk, or None.
    """
    env_path = os.environ.get("CHROME_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    if os.path.exists(DEFAULT_CHROME_PATH):
        return DEFAULT_CHROME_PATH

    for path in FALLBACK_SYSTEM_CHROME_PATHS:
        if os.path.exists(path):
            return path

    if os.path.exists(FALLBACK_EDGE_PATH):
        return FALLBACK_EDGE_PATH

    return None
