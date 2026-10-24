"""
Google Sheets API Client with OAuth Auto-Refresh and Subprocess CLI Fallback.

Provides:
- Direct HTTPS REST operations on Google Sheets v4 API
- Transparent OAuth2 token refresh on HTTP 401 using stored refresh token
- Subprocess CLI fallback via gsheets.cmd
- Exponential backoff on HTTP 429 rate limits
- Clean offline / mock mode for unit and boundary testing
"""

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_TOKEN_PATH = r"C:\Users\rishi\.gemini\antigravity\plugin_data\gsheets\token.json"
DEFAULT_CLI_PATH = r"C:\Users\rishi\.gemini\config\plugins\gsheets\skills\gsheets\scripts\gsheets.cmd"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"


def validate_spreadsheet_id(spreadsheet_id: str) -> None:
    """Validate Google Spreadsheet ID format (non-empty, minimum length, no whitespace)."""
    if not spreadsheet_id or not isinstance(spreadsheet_id, str):
        raise ValueError("Spreadsheet ID must be a non-empty string.")
    s_id = spreadsheet_id.strip()
    if len(s_id) < 20 or " " in s_id:
        raise ValueError(f"Invalid spreadsheet ID: '{spreadsheet_id}'. Must be at least 20 chars without spaces.")


def compute_exponential_backoff(attempt: int, base: float = 1.0, max_backoff: float = 32.0) -> float:
    """Calculate exponential backoff delay for retry handling."""
    delay = base * (2 ** attempt)
    return min(delay, max_backoff)


def normalize_range_key(range_str: str) -> str:
    """Normalize range string (strip outer quotes around tab name for dictionary key lookup)."""
    if not range_str:
        return ""
    r = range_str.strip()
    if "!" in r:
        tab, cells = r.split("!", 1)
        tab_clean = tab.strip("'\"")
        return f"{tab_clean}!{cells.strip()}"
    return r.strip("'\"")


class SheetsClient:
    """
    Direct REST API Google Sheets Client supporting OAuth auto-refresh,
    subprocess CLI fallback, and in-memory offline testing mode.
    """

    def __init__(
        self,
        token_path: Optional[str] = None,
        cli_path: Optional[str] = None,
        offline_mode: bool = False,
        mock_data: Optional[Dict[str, List[List[Any]]]] = None,
        timeout: float = 30.0,
    ) -> None:
        self.token_path = token_path or DEFAULT_TOKEN_PATH
        self.cli_path = cli_path or DEFAULT_CLI_PATH
        self.offline_mode = offline_mode
        self.timeout = timeout

        # In-memory mock storage and grid simulation for offline testing
        self.mock_data: Dict[str, List[List[Any]]] = {}
        self._tab_grids: Dict[str, List[List[Any]]] = {}

        if mock_data:
            for k, v in mock_data.items():
                norm_k = normalize_range_key(k)
                self.mock_data[norm_k] = [list(r) for r in v]
                tab = norm_k.split("!")[0] if "!" in norm_k else norm_k
                if tab not in self._tab_grids:
                    self._tab_grids[tab] = []
                start_row = 1
                if "!" in norm_k:
                    cells = norm_k.split("!")[1]
                    m = re.search(r"^[A-Za-z]+(\d+)", cells)
                    if m:
                        start_row = int(m.group(1))
                while len(self._tab_grids[tab]) < start_row - 1:
                    self._tab_grids[tab].append([])
                for row_idx, r in enumerate(v):
                    target_idx = start_row - 1 + row_idx
                    if target_idx < len(self._tab_grids[tab]):
                        self._tab_grids[tab][target_idx] = list(r)
                    else:
                        self._tab_grids[tab].append(list(r))

        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.client_id: Optional[str] = None
        self.client_secret: Optional[str] = None
        self.scopes: List[str] = []
        self.token_refresh_count: int = 0

        if not self.offline_mode:
            self._load_token()

    def _load_token(self) -> None:
        """Load credentials from token JSON file."""
        if not os.path.exists(self.token_path):
            self.offline_mode = True
            return

        try:
            with open(self.token_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.client_id = data.get("client_id")
            self.client_secret = data.get("client_secret")
            self.scopes = data.get("scopes", [])

            token_obj = data.get("token", {})
            self.access_token = token_obj.get("access_token")
            self.refresh_token = token_obj.get("refresh_token")
        except Exception:
            self.offline_mode = True

    def refresh_access_token(self) -> str:
        """
        Refresh OAuth access token using stored refresh_token, client_id, and client_secret.
        Updates self.access_token and saves back to token file if writable.
        """
        if not self.refresh_token or not self.client_id or not self.client_secret:
            raise RuntimeError("Missing OAuth refresh token, client_id, or client_secret.")

        body = urllib.parse.urlencode({
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }).encode("utf-8")

        req = urllib.request.Request(
            TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            new_access_token = data.get("access_token")
            if not new_access_token:
                raise RuntimeError("Failed to obtain refreshed access token from Google OAuth endpoint.")

            self.access_token = new_access_token
            self.token_refresh_count += 1

            # Update on disk if feasible
            if os.path.exists(self.token_path):
                try:
                    with open(self.token_path, "r", encoding="utf-8") as f:
                        file_data = json.load(f)
                    if "token" in file_data:
                        file_data["token"]["access_token"] = new_access_token
                        if "expires_in" in data:
                            file_data["token"]["expires_in"] = data["expires_in"]
                    with open(self.token_path, "w", encoding="utf-8") as f:
                        json.dump(file_data, f, indent=2)
                except Exception:
                    pass

            return new_access_token

    def _get_headers(self) -> Dict[str, str]:
        """Generate Authorization and content headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _execute_request(
        self,
        method: str,
        url: str,
        body: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Execute HTTPS REST call with automatic token refresh on HTTP 401
        and exponential backoff on HTTP 429.
        """
        data_bytes = json.dumps(body).encode("utf-8") if body is not None else None

        for attempt in range(max_retries):
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers=self._get_headers(),
                method=method,
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_bytes = resp.read()
                    if not resp_bytes:
                        return {}
                    return json.loads(resp_bytes.decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    # Token expired -> Refresh once and retry
                    self.refresh_access_token()
                    continue
                elif e.code == 429:
                    # Rate limit -> Exponential backoff
                    delay = compute_exponential_backoff(attempt)
                    time.sleep(delay)
                    continue
                else:
                    raise
            except urllib.error.URLError:
                if attempt == max_retries - 1:
                    raise
                time.sleep(compute_exponential_backoff(attempt))

        raise RuntimeError(f"HTTP request failed after {max_retries} attempts.")

    def _cli_read_range(self, sheet_id: str, range_str: str) -> List[List[Any]]:
        """Fallback to gsheets.cmd readonly read subprocess."""
        if not os.path.exists(self.cli_path):
            raise FileNotFoundError(f"CLI script not found at {self.cli_path}")

        cmd = [self.cli_path, "readonly", "read", sheet_id, range_str, "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"CLI command failed with code {proc.returncode}: {proc.stderr}")

        try:
            data = json.loads(proc.stdout)
            return data.get("values", [])
        except Exception:
            raise RuntimeError(f"Failed to parse CLI output as JSON: {proc.stdout}")

    def read_range(self, sheet_id: str, range_str: str) -> List[List[Any]]:
        """
        Read cell values for a specified range (e.g. "'Leads Tracker'!A1:U50").
        Returns 2D list of row values.
        """
        validate_spreadsheet_id(sheet_id)

        if self.offline_mode:
            norm_key = normalize_range_key(range_str)
            tab_name = norm_key.split("!")[0] if "!" in norm_key else norm_key
            if tab_name in self._tab_grids and self._tab_grids[tab_name]:
                start_row = 1
                end_row = None
                if "!" in norm_key:
                    cells = norm_key.split("!")[1]
                    parts = cells.split(":")
                    m_start = re.search(r"(\d+)", parts[0])
                    if m_start:
                        start_row = int(m_start.group(1))
                    if len(parts) > 1:
                        m_end = re.search(r"(\d+)", parts[1])
                        if m_end:
                            end_row = int(m_end.group(1))

                grid = self._tab_grids[tab_name]
                start_idx = max(0, start_row - 1)
                end_idx = end_row if end_row is not None else len(grid)
                sliced = grid[start_idx:end_idx]
                return [list(r) for r in sliced if r]

            if norm_key in self.mock_data:
                return [list(r) for r in self.mock_data[norm_key]]
            return []

        encoded_range = urllib.parse.quote(range_str)
        url = f"{SHEETS_API_BASE}/{sheet_id}/values/{encoded_range}?valueRenderOption=FORMATTED_VALUE"

        try:
            result = self._execute_request("GET", url)
            return result.get("values", [])
        except Exception:
            if os.path.exists(self.cli_path):
                return self._cli_read_range(sheet_id, range_str)
            raise

    def append_rows(
        self,
        sheet_id: str,
        range_str: str,
        values: List[List[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> Dict[str, Any]:
        """
        Append rows to a specified sheet/range using Sheets v4 API.
        """
        validate_spreadsheet_id(sheet_id)

        if self.offline_mode:
            norm_key = normalize_range_key(range_str)
            tab_name = norm_key.split("!")[0] if "!" in norm_key else norm_key
            if tab_name not in self._tab_grids:
                self._tab_grids[tab_name] = []

            start_len = len(self._tab_grids[tab_name])
            for r in values:
                self._tab_grids[tab_name].append(list(r))
            return {
                "spreadsheetId": sheet_id,
                "tableRange": range_str,
                "updates": {
                    "updatedRows": len(values),
                    "updatedColumns": max(len(r) for r in values) if values else 0,
                    "updatedCells": sum(len(r) for r in values),
                    "updatedRange": f"{tab_name}!A{start_len + 1}:U{start_len + len(values)}",
                },
            }

        encoded_range = urllib.parse.quote(range_str)
        url = f"{SHEETS_API_BASE}/{sheet_id}/values/{encoded_range}:append?valueInputOption={value_input_option}"
        payload = {"values": values}
        return self._execute_request("POST", url, body=payload)

    def update_range(
        self,
        sheet_id: str,
        range_str: str,
        values: List[List[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> Dict[str, Any]:
        """
        Update a specific cell range with provided values.
        """
        validate_spreadsheet_id(sheet_id)

        if self.offline_mode:
            norm_key = normalize_range_key(range_str)
            self.mock_data[norm_key] = [list(r) for r in values]
            tab_name = norm_key.split("!")[0] if "!" in norm_key else norm_key
            if tab_name not in self._tab_grids:
                self._tab_grids[tab_name] = []

            start_row = 1
            if "!" in norm_key:
                cells = norm_key.split("!")[1]
                parts = cells.split(":")
                m = re.search(r"(\d+)", parts[0])
                if m:
                    start_row = int(m.group(1))

            while len(self._tab_grids[tab_name]) < start_row - 1:
                self._tab_grids[tab_name].append([])

            for row_idx, r in enumerate(values):
                target_idx = start_row - 1 + row_idx
                if target_idx < len(self._tab_grids[tab_name]):
                    self._tab_grids[tab_name][target_idx] = list(r)
                else:
                    self._tab_grids[tab_name].append(list(r))

            return {
                "spreadsheetId": sheet_id,
                "updatedRange": range_str,
                "updatedRows": len(values),
                "updatedColumns": max(len(r) for r in values) if values else 0,
                "updatedCells": sum(len(r) for r in values),
            }

        encoded_range = urllib.parse.quote(range_str)
        url = f"{SHEETS_API_BASE}/{sheet_id}/values/{encoded_range}?valueInputOption={value_input_option}"
        payload = {"values": values}
        return self._execute_request("PUT", url, body=payload)
