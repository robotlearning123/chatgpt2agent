"""ChatGPT token acquisition — tries multiple sources in order."""

from __future__ import annotations

import json
import subprocess
import time
import webbrowser
from pathlib import Path


# --------------------------------------------------------------------------- #
#  Token sources
# --------------------------------------------------------------------------- #


def _from_codex() -> dict | None:
    """Reuse token from Codex CLI (~/.codex/auth.json)."""
    p = Path.home() / ".codex" / "auth.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        token = (
            (data.get("tokens") or {}).get("access_token")
            or data.get("accessToken")
            or data.get("access_token")
        )
        if token:
            return {"access_token": token, "source": "codex"}
    except Exception:
        pass
    return None


def _from_saved() -> dict | None:
    """Reuse previously saved token."""
    p = Path.home() / ".openai-mcp" / "token.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        token = data.get("access_token")
        if token:
            return {"access_token": token, "source": "saved"}
    except Exception:
        pass
    return None


def _from_browser() -> dict | None:
    """Open ChatGPT in browser, ask user to paste the token."""
    print()
    print("  Opening chat.openai.com — please log in if needed.")
    print()
    print("  After logging in, open DevTools (F12 / Cmd+Option+I) and run:")
    print()
    print(
        '    copy(JSON.parse(localStorage["@@auth0spajs@@::..."] || "{}").body?.access_token'
    )
    print("  OR go to:")
    print("    Application → Cookies → __Secure-next-auth.session-token")
    print()
    print("  Then paste the token below.")
    print("  (Alternatively run: openai-mcp login --browser for automatic extraction)")
    print()
    webbrowser.open("https://chat.openai.com")
    token = input("  Paste access_token (or session token): ").strip()
    if token:
        return {"access_token": token, "source": "browser"}
    return None


def _from_browser_use() -> dict | None:
    """Extract token automatically using browser-use CLI (if installed)."""
    if subprocess.run(["which", "browser-use"], capture_output=True).returncode != 0:
        return None

    print("  browser-use detected — attempting automatic token extraction...")
    try:
        # Open ChatGPT and wait for login
        subprocess.run(
            ["browser-use", "open", "https://chat.openai.com"],
            timeout=30,
        )
        time.sleep(3)
        input("  Log in if needed, then press Enter to extract token... ")

        # Try localStorage first
        result = subprocess.run(
            [
                "browser-use",
                "eval",
                "JSON.stringify(Object.entries(localStorage).filter(([k]) => k.includes('auth0')))",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        raw = result.stdout.strip()
        if raw and "access_token" in raw:
            entries = json.loads(raw)
            for _, v in entries:
                try:
                    body = json.loads(v).get("body", {})
                    token = body.get("access_token")
                    if token:
                        return {"access_token": token, "source": "browser-use"}
                except Exception:
                    pass

        # Try cookies fallback
        result = subprocess.run(
            ["browser-use", "cookies", "get", "--url", "https://chat.openai.com"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        cookies = json.loads(result.stdout or "[]")
        for c in cookies:
            if "session-token" in c.get("name", ""):
                return {"access_token": c["value"], "source": "browser-use-cookie"}

    except Exception as e:
        print(f"  browser-use extraction failed: {e}")
    return None


# --------------------------------------------------------------------------- #
#  Public API
# --------------------------------------------------------------------------- #


def get_token(interactive: bool = True) -> str:
    """Return a valid ChatGPT access token, trying sources in priority order."""
    for fn in [_from_saved, _from_codex, _from_browser_use]:
        result = fn()
        if result:
            print(f"  ✓ Token found ({result['source']})")
            return result["access_token"]

    if not interactive:
        raise RuntimeError("No ChatGPT token found. Run: openai-mcp setup")

    result = _from_browser()
    if not result:
        raise RuntimeError("Token acquisition cancelled.")

    # Save for future use
    save_dir = Path.home() / ".openai-mcp"
    save_dir.mkdir(exist_ok=True)
    (save_dir / "token.json").write_text(json.dumps(result, indent=2))
    print("  Token saved to ~/.openai-mcp/token.json")
    return result["access_token"]
