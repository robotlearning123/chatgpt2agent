"""One-command client registration: write gpt2agent into popular MCP-capable
agent config files (Claude Code, Codex, …) plus the Claude Code skill bundle.

Used by ``gpt2agent install --client {claude-code,codex,all}``. Each
register function is idempotent — running twice yields the same final
config — and writes a sibling ``.bak-gpt2agent`` backup of the prior
contents before any change.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

# ── ANSI ──────────────────────────────────────────────────────────────────
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _ok(msg: str) -> None:
    print(f"  {_GREEN}✓{_RESET} {msg}")


def _info(msg: str) -> None:
    print(f"  {_YELLOW}→{_RESET} {msg}")


def _warn(msg: str) -> None:
    print(f"  {_YELLOW}!{_RESET} {msg}")


def _err(msg: str) -> None:
    print(f"  {_RED}✗{_RESET} {msg}", file=sys.stderr)


def _h1(msg: str) -> None:
    print(f"\n{_BOLD}{msg}{_RESET}")


# ── shared ─────────────────────────────────────────────────────────────────


def _backup(path: Path) -> Path | None:
    """Snapshot ``path`` to ``path.bak-gpt2agent`` so the user can undo."""
    if not path.exists():
        return None
    bak = path.with_name(path.name + ".bak-gpt2agent")
    bak.write_bytes(path.read_bytes())
    return bak


def _atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` via a temp file in the same directory.

    Preserves the existing file's mode bits across the rename. For new files,
    uses 0o600 — agent-config files (~/.claude.json, ~/.codex/config.toml)
    contain MCP server commands that the agent will exec, so they should not
    be world-readable on shared systems.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    tmp.write_text(content)
    try:
        if path.exists():
            tmp.chmod(path.stat().st_mode)
        else:
            tmp.chmod(0o600)
    except OSError:
        # Best-effort — Windows / non-POSIX filesystems may reject chmod.
        pass
    tmp.replace(path)


def _stdio_entry() -> dict[str, Any]:
    return {
        "type": "stdio",
        "command": "gpt2agent",
        "args": ["run", "--stdio"],
    }


def _http_entry(port: int) -> dict[str, Any]:
    return {"type": "url", "url": f"http://localhost:{port}/mcp"}


# ── Claude Code ────────────────────────────────────────────────────────────


def install_claude_code(
    *,
    transport: str = "stdio",
    http_port: int = 9000,
    server_name: str = "gpt2agent",
    dry_run: bool = False,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Register gpt2agent in ``~/.claude.json`` under ``mcpServers.<server_name>``.

    Preserves all other fields of the existing config (the file is large and
    holds unrelated state — tips history, conversation tracking, etc.).
    """
    cfg_path = config_path or Path.home() / ".claude.json"

    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text())
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{cfg_path} is not valid JSON ({exc}). Refusing to overwrite — "
                "open it in an editor and either repair or move it aside."
            )
    else:
        data = {}

    servers = data.setdefault("mcpServers", {})
    entry = _stdio_entry() if transport == "stdio" else _http_entry(http_port)
    prior = servers.get(server_name)
    servers[server_name] = entry

    if prior == entry:
        _info(f"claude-code: {cfg_path} already has {server_name!r} entry (no-op)")
        return {"path": cfg_path, "backup": None, "changed": False}

    if dry_run:
        _info(f"claude-code: would update {cfg_path} mcpServers.{server_name}")
        return {"path": cfg_path, "backup": None, "changed": False}

    backup = _backup(cfg_path)
    _atomic_write(cfg_path, json.dumps(data, indent=2) + "\n")
    _ok(
        f"claude-code: wrote mcpServers.{server_name} to {cfg_path} "
        f"(backup: {backup.name if backup else 'none'})"
    )
    return {"path": cfg_path, "backup": backup, "changed": True}


# ── Codex CLI ──────────────────────────────────────────────────────────────


def _toml_quote(value: str) -> str:
    """Quote a string for TOML basic-string form."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _replace_or_append_toml_section(
    content: str,
    section_name: str,
    new_section_lines: list[str],
) -> str:
    """Replace ``[section_name]`` block in ``content`` or append it.

    A section runs from its ``[header]`` line up to the next ``[header]`` or
    end-of-file. Other sections are preserved verbatim. The new block is
    written as ``[section_name]`` followed by ``new_section_lines``.
    """
    header = f"[{section_name}]"
    new_block = "\n".join([header, *new_section_lines]).strip("\n")

    lines = content.splitlines()
    out: list[str] = []
    i = 0
    found = False
    section_header_re = re.compile(r"^\s*\[[^\[\]]+\]\s*$")

    while i < len(lines):
        line = lines[i]
        if line.strip() == header:
            found = True
            out.append(new_block)
            i += 1
            # Skip prior body until next section header or EOF
            while i < len(lines) and not section_header_re.match(lines[i]):
                i += 1
            continue
        out.append(line)
        i += 1

    if not found:
        trailing_blank = bool(out) and out[-1].strip() == ""
        if not trailing_blank and out:
            out.append("")
        out.append(new_block)

    result = "\n".join(out).rstrip() + "\n"
    return result


def install_codex(
    *,
    server_name: str = "gpt2agent",
    dry_run: bool = False,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Register gpt2agent in ``~/.codex/config.toml`` under ``[mcp_servers.<server_name>]``.

    Preserves all other sections (codex agent definitions, model config, …).
    """
    cfg_path = config_path or Path.home() / ".codex" / "config.toml"
    existing = cfg_path.read_text() if cfg_path.exists() else ""

    section_name = f"mcp_servers.{server_name}"
    new_section = [
        f'command = {_toml_quote("gpt2agent")}',
        'args = ["run", "--stdio"]',
    ]
    new_content = _replace_or_append_toml_section(existing, section_name, new_section)

    if new_content == existing:
        _info(f"codex: {cfg_path} already has [{section_name}] (no-op)")
        return {"path": cfg_path, "backup": None, "changed": False}

    if dry_run:
        _info(f"codex: would write [{section_name}] to {cfg_path}")
        return {"path": cfg_path, "backup": None, "changed": False}

    backup = _backup(cfg_path)
    _atomic_write(cfg_path, new_content)
    _ok(
        f"codex: wrote [{section_name}] to {cfg_path} "
        f"(backup: {backup.name if backup else 'none'})"
    )
    return {"path": cfg_path, "backup": backup, "changed": True}


# ── Claude Code skill bundle ───────────────────────────────────────────────


def install_claude_skill(
    *,
    dst_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Copy the bundled ``deep-research`` skill into ``~/.claude/skills/``.

    The skill calls gpt2agent's ConversationClient directly (bypasses the MCP
    transport) so it works even before restarting Claude Code.
    """
    src = Path(__file__).parent / "skills" / "deep-research"
    if not src.exists():
        _warn("skill bundle not found in package — skipped")
        return {"path": None, "skipped": True}

    dst = (dst_dir or Path.home() / ".claude" / "skills") / "deep-research"

    if dry_run:
        _info(f"skill: would install {src} → {dst}")
        return {"path": dst, "changed": False}

    backup: Path | None = None
    if dst.exists():
        backup = dst.with_name(dst.name + ".bak-gpt2agent")
        if backup.exists():
            shutil.rmtree(backup)
        shutil.move(str(dst), str(backup))

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    # Ensure executable bits on shell scripts (lost on some filesystems)
    for sh in dst.glob("bin/*.sh"):
        sh.chmod(0o755)

    _ok(
        f"skill: installed deep-research → {dst} "
        f"(backup: {backup.name if backup else 'none'})"
    )
    return {"path": dst, "backup": backup, "changed": True}


# ── auto-detect ────────────────────────────────────────────────────────────


def detect_clients() -> list[str]:
    """Return clients whose config locations are present on disk."""
    detected = []
    if (Path.home() / ".claude.json").exists() or (Path.home() / ".claude").exists():
        detected.append("claude-code")
    if (Path.home() / ".codex").exists():
        detected.append("codex")
    return detected


# ── top-level entry point ──────────────────────────────────────────────────


def run_install(
    *,
    client: str = "all",
    transport: str = "stdio",
    http_port: int = 9000,
    install_skill: bool = True,
    dry_run: bool = False,
) -> int:
    """Run the install flow for the chosen client(s)."""
    _h1("gpt2agent install")

    if client == "all":
        targets = detect_clients()
        if not targets:
            _err("No supported clients detected on this machine.")
            _info("Expected one of: ~/.claude.json, ~/.claude/, ~/.codex/")
            return 1
        _info(f"detected: {', '.join(targets)}")
    else:
        targets = [client]

    failures = 0
    for target in targets:
        try:
            if target == "claude-code":
                install_claude_code(
                    transport=transport,
                    http_port=http_port,
                    dry_run=dry_run,
                )
            elif target == "codex":
                install_codex(dry_run=dry_run)
            else:
                _err(f"Unknown client: {target}")
                failures += 1
        except Exception as exc:  # noqa: BLE001
            _err(f"{target}: {exc}")
            failures += 1

    if install_skill and "claude-code" in targets:
        try:
            install_claude_skill(dry_run=dry_run)
        except Exception as exc:  # noqa: BLE001
            _err(f"skill install: {exc}")
            failures += 1

    if failures:
        _err(f"completed with {failures} failure(s)")
        return 1

    if not dry_run:
        _h1("Next steps")
        if "claude-code" in targets:
            print("  • Restart Claude Code so it spawns the new MCP subprocess")
        if "codex" in targets:
            print("  • Codex will spawn gpt2agent on next run; nothing else to do")
        print("  • Try:  gpt2agent run --stdio  # (manual stdio smoke test)")
    return 0
