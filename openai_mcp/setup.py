"""openai-mcp setup wizard — one command, done."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import time
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
    p = Path.home() / ".codex" / "auth.json"
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
    p = Path.home() / ".openai-mcp" / "token.json"
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
    raise SystemExit("Login cancelled. Re-run: openai-mcp setup")


def save_token(token: str) -> None:
    d = Path.home() / ".openai-mcp"
    d.mkdir(exist_ok=True)
    (d / "token.json").write_text(json.dumps({"access_token": token}))


# ── plan detection ──────────────────────────────────────────────────────────


def detect_plan() -> str:
    """Probe chatgpt.com/backend-api/me via BackendClient. Returns pro/plus/free."""
    try:
        from openai_mcp.backend import BackendClient

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

MCP_CONFIG_PATH = Path.home() / ".openai-mcp" / "config.toml"
MCP_PORT = 9000


def write_mcp_config(plan: str) -> None:
    chat_model = "gpt-5-5-pro" if plan == "pro" else "gpt-5-3"
    cfg = f"""[server]
host = "0.0.0.0"
port = {MCP_PORT}

[models]
chat = "{chat_model}"
"""
    MCP_CONFIG_PATH.write_text(cfg)


def _port_open(port: int) -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def ensure_mcp_server() -> None:
    h1("Step 2 — Start MCP server")

    if _port_open(MCP_PORT):
        ok(f"MCP server already running on :{MCP_PORT}")
        return

    log = open(Path.home() / ".openai-mcp" / "mcp.log", "w")
    subprocess.Popen(
        [sys.executable, "-m", "openai_mcp.server", "--config", str(MCP_CONFIG_PATH)],
        stdout=log,
        stderr=log,
        start_new_session=True,
    )

    for _ in range(15):
        if _port_open(MCP_PORT):
            ok(f"MCP server started on :{MCP_PORT}")
            return
        time.sleep(1)

    raise SystemExit("MCP server failed to start. Check ~/.openai-mcp/mcp.log")


def ensure_launchagent() -> None:
    """Install macOS LaunchAgent for persistence."""
    if platform.system() != "Darwin":
        return

    label = "com.user.openai-mcp"
    plist = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    binary = shutil.which("openai-mcp") or sys.executable

    cmd = (
        f"        <string>{binary}</string>\n"
        f"        <string>--config</string>\n"
        f"        <string>{MCP_CONFIG_PATH}</string>"
    )

    plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
    <key>Label</key><string>{label}</string>
    <key>ProgramArguments</key><array>
{cmd}
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>{Path.home()}/.openai-mcp/mcp.log</string>
    <key>StandardErrorPath</key><string>{Path.home()}/.openai-mcp/mcp.log</string>
</dict></plist>""")

    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    subprocess.run(["launchctl", "load", str(plist)], capture_output=True)


# ── agent CLI registration ───────────────────────────────────────────────────


def register_claude_code() -> bool:
    claude_json = Path.home() / ".claude.json"
    if not shutil.which("claude") and not claude_json.exists():
        return False

    try:
        data = json.loads(claude_json.read_text()) if claude_json.exists() else {}
    except Exception:
        data = {}

    data.setdefault("mcpServers", {})
    data["mcpServers"]["openai"] = {
        "type": "url",
        "url": f"http://localhost:{MCP_PORT}/mcp",
    }
    claude_json.write_text(json.dumps(data, indent=2))
    return True


def register_agents() -> None:
    h1("Step 3 — Register with agent CLIs")

    if register_claude_code():
        ok("Claude Code → ~/.claude.json updated")
        info("Restart Claude Code to activate tools")
    else:
        info("Claude Code not found (skipped)")


# ── final summary ────────────────────────────────────────────────────────────


def print_summary(plan: str) -> None:
    print()
    print(f"{BOLD}{'─' * 50}{RESET}")
    print(f"{GREEN}{BOLD}  Done!{RESET}  ChatGPT {plan.capitalize()} is ready.")
    print(f"{'─' * 50}")
    print()
    print(f"  Plan:   ChatGPT {plan.capitalize()}")
    print(f"  URL:    http://localhost:{MCP_PORT}/mcp")
    print()
    print("  Tools available in your agent:")
    print("    chat, deep_research, deep_research_heavy")
    print("    account_status, list_models")
    print("    memory_list, memory_search, custom_instructions_get")
    print("    custom_instructions_set, codex_task_create")
    print("    list_codex_envs, list_codex_tasks")
    print("    list_custom_gpts, list_conversations, list_tasks, list_apps")
    print()
    print("  Logs:   ~/.openai-mcp/mcp.log")
    print()


# ── entry point ──────────────────────────────────────────────────────────────


def run_setup() -> None:
    print(f"\n{BOLD}openai-mcp setup{RESET}")
    print("Use your ChatGPT Plus/Pro in Claude Code and other AI tools.\n")

    try:
        token = get_token()
        save_token(token)

        h1("Detecting plan...")
        plan = detect_plan()
        ok(f"ChatGPT {plan.capitalize()} detected")

        write_mcp_config(plan)
        ensure_mcp_server()
        if platform.system() == "Darwin":
            ensure_launchagent()
            ok("Auto-start enabled (LaunchAgent)")

        register_agents()
        print_summary(plan)

    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(1)
