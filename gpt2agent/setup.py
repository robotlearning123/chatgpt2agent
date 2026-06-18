"""gpt2agent setup wizard — one command, done."""

from __future__ import annotations

import json
import os
import sys
import webbrowser
from pathlib import Path

# ── colours ────────────────────────────────────────────────────────────────
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(msg):
    print(f"  {GREEN}✓{RESET} {msg}")


def info(msg):
    print(f"  {YELLOW}→{RESET} {msg}")


def err(msg):
    print(f"  {RED}✗{RESET} {msg}")


def h1(msg):
    print(f"\n{BOLD}{msg}{RESET}")


# ── token acquisition ───────────────────────────────────────────────────────


def _token_from_codex() -> str | None:
    codex_home = os.environ.get("CODEX_HOME")
    p = (Path(codex_home) if codex_home else Path.home() / ".codex") / "auth.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
        tokens = d.get("tokens") or {}
        return (
            tokens.get("access_token") or d.get("accessToken") or d.get("access_token")
        )
    except Exception:
        return None


def _token_from_saved() -> str | None:
    p = Path.home() / ".gpt2agent" / "token.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
        return d.get("access_token")
    except Exception:
        return None


def _token_via_manual() -> str | None:
    """Open browser + ask user to paste token."""
    print()
    print("  Easiest path: install Codex CLI and run `codex login` — we'll")
    print("  pick up ~/.codex/auth.json automatically next time.")
    print()
    print("  Or paste a token manually:")
    print("    1. Press F12 → Console on chat.openai.com")
    print("    2. Paste + run:")
    print()
    print("       copy((Object.entries(localStorage).find(([k])=>")
    print(
        '         k.includes(\'auth0\'))||[])[1]?.match(/"access_token":"([^"]+)"/) ?.[1])'
    )
    print()
    webbrowser.open("https://chat.openai.com")
    token = input("  Paste token here (or empty to cancel): ").strip()
    return token or None


def get_token() -> str:
    h1("Step 1 — Locate ChatGPT token")

    if t := _token_from_codex():
        ok("Found Codex CLI token (~/.codex/auth.json)")
        return t
    if t := _token_from_saved():
        ok("Using saved token")
        return t
    info("No Codex token — falling back to manual paste")
    if t := _token_via_manual():
        ok("Token received")
        return t
    raise SystemExit("Login cancelled. Re-run: gpt2agent setup")


def save_token(token: str) -> None:
    d = Path.home() / ".gpt2agent"
    d.mkdir(exist_ok=True)
    p = d / "token.json"
    p.write_text(json.dumps({"access_token": token}))
    p.chmod(0o600)


# ── plan detection ──────────────────────────────────────────────────────────


def detect_plan() -> str:
    """Probe chatgpt.com/backend-api/me via BackendClient. Returns pro/plus/free."""
    try:
        from gpt2agent.backend import BackendClient

        bc = BackendClient()
        acct = bc.get("/backend-api/accounts/check/v4-2023-04-27")
        for a in (acct.get("accounts") or {}).values():
            ent = a.get("entitlement") or {}
            plan = ent.get("subscription_plan", "")
            if "pro" in plan:
                return "pro"
            if "plus" in plan:
                return "plus"
    except Exception:
        pass
    return "plus"  # assume plus if probe fails


# ── MCP server ───────────────────────────────────────────────────────────────

MCP_CONFIG_PATH = Path.home() / ".gpt2agent" / "config.toml"
MCP_PORT = 9000


def write_mcp_config(plan: str) -> None:
    chat_model = "gpt-5-5-pro" if plan == "pro" else "gpt-5-3"
    cfg = f"""[server]
# Loopback only — the HTTP transport is unauthenticated and proxies your full
# ChatGPT account. To expose it, set host explicitly AND GPT2AGENT_ALLOW_REMOTE=1.
host = "127.0.0.1"
port = {MCP_PORT}

[models]
chat = "{chat_model}"
"""
    MCP_CONFIG_PATH.write_text(cfg)


# ── final summary ────────────────────────────────────────────────────────────


def print_summary(plan: str) -> None:
    print()
    print(f"{BOLD}{'─' * 50}{RESET}")
    print(f"{GREEN}{BOLD}  Done!{RESET}  ChatGPT {plan.capitalize()} is ready.")
    print(f"{'─' * 50}")
    print()
    print(f"  Plan:      ChatGPT {plan.capitalize()}")
    print("  Transport: stdio (local subprocess; not network-exposed)")
    print()
    print("  Restart your MCP client (Claude Code / Cursor / …) to load the tools.")
    print("  Then try the `account_status` or `chat` tool from your agent.")
    print()


# ── entry point ──────────────────────────────────────────────────────────────


def run_setup() -> None:
    print(f"\n{BOLD}gpt2agent setup{RESET}")
    print("Use your ChatGPT Plus/Pro in Claude Code and other AI tools.\n")

    try:
        token = get_token()
        save_token(token)

        h1("Detecting plan...")
        plan = detect_plan()
        ok(f"ChatGPT {plan.capitalize()} detected")

        # Persist a model default, then register over stdio — the same safe path
        # as `gpt2agent install`. (No background HTTP daemon / LaunchAgent / legacy
        # `openai` URL entry: the stdio transport is what every MCP client wants and
        # avoids exposing an unauthenticated account proxy.)
        write_mcp_config(plan)
        from gpt2agent.install import run_install

        rc = run_install(client="all", transport="stdio")
        if rc != 0:
            print()
            print(f"{RED}  Token saved, but client registration did not fully "
                  f"succeed (see messages above).{RESET}")
            print("  Fix the reported client(s) and re-run:  gpt2agent install")
            sys.exit(rc)
        print_summary(plan)

    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(1)
