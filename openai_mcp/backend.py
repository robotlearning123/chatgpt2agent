"""Direct chatgpt.com backend client — no proxy, no API key."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from curl_cffi import requests


_BASE = "https://chatgpt.com"
_CLIENT_VERSION = "prod-be885abbfcfe7b1f511e88b3003d9ee44757fbad"
_CLIENT_BUILD = "5955942"


def _load_token() -> str:
    p = Path.home() / ".codex" / "auth.json"
    if not p.exists():
        raise RuntimeError("~/.codex/auth.json not found — run `codex login` first")
    try:
        data = json.loads(p.read_text())
        token = (data.get("tokens") or {}).get("access_token")
        if not token:
            raise RuntimeError("tokens.access_token missing in ~/.codex/auth.json")
        return token
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Failed to read ~/.codex/auth.json: {exc}") from exc


class BackendClient:
    def __init__(self) -> None:
        token = _load_token()
        self._session = requests.Session(impersonate="edge101", verify=True)
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 Chrome/143 Edg/143",
                "Authorization": f"Bearer {token}",
                "OAI-Device-Id": str(uuid.uuid4()),
                "OAI-Session-Id": str(uuid.uuid4()),
                "OAI-Language": "en-US",
                "OAI-Client-Version": _CLIENT_VERSION,
                "OAI-Client-Build-Number": _CLIENT_BUILD,
                "Origin": _BASE,
                "Referer": _BASE + "/",
                "Accept": "*/*",
            }
        )

    def get(
        self,
        path: str,
        target_path: str | None = None,
        target_route: str | None = None,
    ) -> Any:
        extra: dict[str, str] = {}
        if target_path is not None:
            extra["X-OpenAI-Target-Path"] = target_path
        if target_route is not None:
            extra["X-OpenAI-Target-Route"] = target_route

        r = self._session.get(_BASE + path, headers=extra, timeout=20)

        if r.status_code == 401:
            raise RuntimeError("401 Unauthorized — token expired, run `codex login`")
        if r.status_code == 403:
            raise RuntimeError(f"403 Forbidden for {path}")
        if r.status_code == 404:
            raise RuntimeError(f"404 Not Found: {path}")
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} for {path}")

        return r.json()
