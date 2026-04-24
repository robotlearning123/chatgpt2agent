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
    """Load the ChatGPT bearer token from either codex login or the setup wizard.

    Search order:
      1. ``~/.codex/auth.json`` with ``tokens.access_token`` (codex login)
      2. ``~/.openai-mcp/token.json`` with ``token`` (flat) OR
         ``tokens.access_token`` (nested) — written by ``openai-mcp setup``

    Raises RuntimeError only if neither source yields a token.
    """
    # Source 1: codex login
    codex_path = Path.home() / ".codex" / "auth.json"
    codex_err: str | None = None
    if codex_path.exists():
        try:
            data = json.loads(codex_path.read_text())
            token = (data.get("tokens") or {}).get("access_token")
            if token:
                return token
            codex_err = "tokens.access_token missing in ~/.codex/auth.json"
        except (json.JSONDecodeError, OSError) as exc:
            codex_err = f"Failed to read ~/.codex/auth.json: {exc}"

    # Source 2: openai-mcp setup wizard
    wizard_path = Path.home() / ".openai-mcp" / "token.json"
    wizard_err: str | None = None
    if wizard_path.exists():
        try:
            data = json.loads(wizard_path.read_text())
            # Accept flat {"token": ...} or {"access_token": ...} or nested {"tokens": {"access_token": ...}}
            token = (
                data.get("token")
                or data.get("access_token")
                or (data.get("tokens") or {}).get("access_token")
            )
            if token:
                return token
            wizard_err = "token/access_token/tokens.access_token missing in ~/.openai-mcp/token.json"
        except (json.JSONDecodeError, OSError) as exc:
            wizard_err = f"Failed to read ~/.openai-mcp/token.json: {exc}"

    # Nothing worked — surface the most informative error we have.
    if codex_err or wizard_err:
        details = "; ".join(e for e in (codex_err, wizard_err) if e)
        raise RuntimeError(
            f"No ChatGPT token found — run `codex login` or `openai-mcp setup` "
            f"({details})"
        )
    raise RuntimeError(
        "No ChatGPT token found — run `codex login` or `openai-mcp setup` "
        "(checked ~/.codex/auth.json and ~/.openai-mcp/token.json)"
    )


_CHROME_131_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class BackendClient:
    def __init__(self) -> None:
        token = _load_token()
        # Keep TLS fingerprint + User-Agent aligned across backend / sentinel /
        # conversation streams. Cloudflare's bot manager cross-checks them and
        # will 403 mixed fingerprints.
        self._session = requests.Session(impersonate="chrome131", verify=True)
        self._session.headers.update(
            {
                "User-Agent": _CHROME_131_UA,
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

    def post(
        self,
        path: str,
        json: Any = None,
        target_path: str | None = None,
        target_route: str | None = None,
    ) -> Any:
        extra: dict[str, str] = {"Content-Type": "application/json"}
        if target_path is not None:
            extra["X-OpenAI-Target-Path"] = target_path
        if target_route is not None:
            extra["X-OpenAI-Target-Route"] = target_route

        r = self._session.post(_BASE + path, headers=extra, json=json, timeout=30)

        if r.status_code == 401:
            raise RuntimeError("401 Unauthorized — token expired, run `codex login`")
        if r.status_code == 403:
            raise RuntimeError(f"403 Forbidden for {path}")
        if r.status_code == 404:
            raise RuntimeError(f"404 Not Found: {path}")
        if r.status_code == 405:
            raise RuntimeError(f"405 Method Not Allowed: {path}")
        if not (200 <= r.status_code < 300):
            raise RuntimeError(f"HTTP {r.status_code} for {path}: {r.text[:200]}")

        if not r.text.strip():
            return None
        try:
            return r.json()
        except Exception as exc:
            raise RuntimeError(
                f"Expected JSON from {path} but got non-JSON 2xx response: "
                f"{r.text[:200]!r}"
            ) from exc
