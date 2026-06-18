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

    # Migrate stale 0.0.1-era "openai" entry that points at the old binary.
    # The openai-mcp pipx app is gone post-rename, so a leftover entry is a
    # broken pointer Claude Code will spawn-and-fail on every restart.
    legacy = servers.get("openai")
    legacy_removed = False
    if (
        server_name != "openai"
        and isinstance(legacy, dict)
        and legacy.get("command") == "openai-mcp"
    ):
        del servers["openai"]
        legacy_removed = True

    if prior == entry and not legacy_removed:
        _info(f"claude-code: {cfg_path} already has {server_name!r} entry (no-op)")
        return {"path": cfg_path, "backup": None, "changed": False}

    if dry_run:
        _info(f"claude-code: would update {cfg_path} mcpServers.{server_name}")
        if legacy_removed:
            _info("claude-code: would also drop stale legacy 'openai' entry")
        return {"path": cfg_path, "backup": None, "changed": False}

    backup = _backup(cfg_path)
    _atomic_write(cfg_path, json.dumps(data, indent=2) + "\n")
    _ok(
        f"claude-code: wrote mcpServers.{server_name} to {cfg_path} "
        f"(backup: {backup.name if backup else 'none'})"
    )
    if legacy_removed:
        _ok("claude-code: removed stale legacy 'openai' entry (pointed at gone openai-mcp binary)")
    return {"path": cfg_path, "backup": backup, "changed": True}


# ── Codex CLI ──────────────────────────────────────────────────────────────


def _toml_quote(value: str) -> str:
    """Quote a string for TOML basic-string form."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _remove_toml_section(content: str, section_name: str) -> str:
    """Remove the ``[section_name]`` block from TOML content. No-op if absent.

    A section runs from its ``[header]`` line up to the next ``[header]`` or
    end-of-file. Other sections are preserved verbatim.
    """
    header = f"[{section_name}]"
    section_header_re = re.compile(r"^\s*\[[^\[\]]+\]\s*$")
    out: list[str] = []
    skipping = False
    for line in content.splitlines():
        if line.strip() == header:
            skipping = True
            continue
        if skipping:
            if section_header_re.match(line):
                skipping = False
                # fall through to keep this header line
            else:
                continue
        out.append(line)
    return "\n".join(out).rstrip() + "\n" if out else ""


def _legacy_codex_openai_present(content: str) -> bool:
    """True iff content has a ``[mcp_servers.openai]`` section whose
    ``command`` is the renamed-away ``openai-mcp`` binary.
    """
    try:
        import tomllib
    except ImportError:  # Python 3.10 fallback
        import tomli as tomllib  # type: ignore
    try:
        parsed = tomllib.loads(content)
    except Exception:
        return False
    legacy = (parsed.get("mcp_servers") or {}).get("openai") or {}
    return legacy.get("command") == "openai-mcp"


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

    # Drop a stale 0.0.1 [mcp_servers.openai] block whose command is the
    # gone openai-mcp binary — Codex would spawn-and-fail on every invocation.
    legacy_removed = False
    if section_name != "mcp_servers.openai" and _legacy_codex_openai_present(new_content):
        new_content = _remove_toml_section(new_content, "mcp_servers.openai")
        legacy_removed = True

    if new_content == existing:
        _info(f"codex: {cfg_path} already has [{section_name}] (no-op)")
        return {"path": cfg_path, "backup": None, "changed": False}

    if dry_run:
        _info(f"codex: would write [{section_name}] to {cfg_path}")
        if legacy_removed:
            _info("codex: would also drop stale legacy [mcp_servers.openai] block")
        return {"path": cfg_path, "backup": None, "changed": False}

    backup = _backup(cfg_path)
    _atomic_write(cfg_path, new_content)
    _ok(
        f"codex: wrote [{section_name}] to {cfg_path} "
        f"(backup: {backup.name if backup else 'none'})"
    )
    if legacy_removed:
        _ok("codex: removed stale legacy [mcp_servers.openai] block")
    return {"path": cfg_path, "backup": backup, "changed": True}


# ── Other MCP hosts (JSON, mcpServers-style) ───────────────────────────────
#
# Cursor, Windsurf, Claude Desktop and friends all use the same
# ``{"<top_key>": {"<server>": {command, args}}}`` JSON shape Claude Code uses —
# only the file path (and, for VS Code/Zed, the top-level key + entry shape)
# differ. ``_install_json_host`` is the shared, idempotent writer; the per-host
# functions just supply path + key + entry.


def _mcp_entry() -> dict[str, Any]:
    """stdio server entry for the mcpServers-style hosts (Cursor/Windsurf/…)."""
    return {"command": "gpt2agent", "args": ["run", "--stdio"]}


def _zed_entry() -> dict[str, Any]:
    """Zed nests the command and uses a ``context_servers`` top-level key."""
    return {"command": {"path": "gpt2agent", "args": ["run", "--stdio"]}, "settings": {}}


def _install_json_host(
    label: str,
    cfg_path: Path,
    *,
    top_key: str,
    entry: dict[str, Any],
    server_name: str = "gpt2agent",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Register gpt2agent in a JSON MCP config file under ``top_key.<server>``.

    Idempotent; preserves every other field; writes a ``.bak-gpt2agent`` backup.
    Used for Cursor, Windsurf, Claude Desktop, and Zed (see callers). VS Code and
    Cline use the same shape but are documented as manual setup (docs/clients.md).
    """
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text() or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{cfg_path} is not valid JSON ({exc}). Refusing to overwrite — "
                "repair it or move it aside, then re-run."
            )
        if not isinstance(data, dict):
            raise RuntimeError(f"{cfg_path} is not a JSON object; refusing to overwrite.")
    else:
        data = {}

    servers = data.setdefault(top_key, {})
    if not isinstance(servers, dict):
        raise RuntimeError(f"{cfg_path}: '{top_key}' is not an object; refusing to overwrite.")
    prior = servers.get(server_name)
    servers[server_name] = entry

    if prior == entry:
        _info(f"{label}: {cfg_path} already has {top_key}.{server_name} (no-op)")
        return {"path": cfg_path, "backup": None, "changed": False}
    if dry_run:
        _info(f"{label}: would write {top_key}.{server_name} to {cfg_path}")
        return {"path": cfg_path, "backup": None, "changed": False}

    backup = _backup(cfg_path)
    _atomic_write(cfg_path, json.dumps(data, indent=2) + "\n")
    _ok(f"{label}: wrote {top_key}.{server_name} to {cfg_path} "
        f"(backup: {backup.name if backup else 'none'})")
    return {"path": cfg_path, "backup": backup, "changed": True}


def install_cursor(*, server_name: str = "gpt2agent", dry_run: bool = False,
                   config_path: Path | None = None) -> dict[str, Any]:
    """Register gpt2agent in Cursor's ``~/.cursor/mcp.json`` (``mcpServers``)."""
    cfg = config_path or Path.home() / ".cursor" / "mcp.json"
    return _install_json_host("cursor", cfg, top_key="mcpServers", entry=_mcp_entry(),
                              server_name=server_name, dry_run=dry_run)


def install_windsurf(*, server_name: str = "gpt2agent", dry_run: bool = False,
                     config_path: Path | None = None) -> dict[str, Any]:
    """Register gpt2agent in Windsurf's ``~/.codeium/windsurf/mcp_config.json``."""
    cfg = config_path or Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
    return _install_json_host("windsurf", cfg, top_key="mcpServers", entry=_mcp_entry(),
                              server_name=server_name, dry_run=dry_run)


def install_claude_desktop(*, server_name: str = "gpt2agent", dry_run: bool = False,
                           config_path: Path | None = None) -> dict[str, Any]:
    """Register gpt2agent in the Claude Desktop config (``mcpServers``)."""
    cfg = config_path or _claude_desktop_config_path()
    return _install_json_host("claude-desktop", cfg, top_key="mcpServers", entry=_mcp_entry(),
                              server_name=server_name, dry_run=dry_run)


def install_zed(*, server_name: str = "gpt2agent", dry_run: bool = False,
                config_path: Path | None = None) -> dict[str, Any]:
    """Register gpt2agent in Zed's ``~/.config/zed/settings.json`` (``context_servers``)."""
    cfg = config_path or Path.home() / ".config" / "zed" / "settings.json"
    return _install_json_host("zed", cfg, top_key="context_servers", entry=_zed_entry(),
                              server_name=server_name, dry_run=dry_run)


def _claude_desktop_config_path() -> Path:
    """Platform-specific Claude Desktop config path."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


# Registry of the JSON hosts beyond claude-code/codex: name → (installer, detect path).
_EXTRA_HOSTS: dict[str, Any] = {
    "cursor": (install_cursor, lambda: Path.home() / ".cursor"),
    "windsurf": (install_windsurf, lambda: Path.home() / ".codeium" / "windsurf"),
    "claude-desktop": (install_claude_desktop, lambda: _claude_desktop_config_path().parent),
    "zed": (install_zed, lambda: Path.home() / ".config" / "zed"),
}


# ── Claude Code skill bundle ───────────────────────────────────────────────


def _install_one_skill(
    name: str,
    src: Path,
    dst_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Copy one skill directory into *dst_dir*."""
    dst = dst_dir / name

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
        f"skill: installed {name} → {dst} "
        f"(backup: {backup.name if backup else 'none'})"
    )
    return {"path": dst, "backup": backup, "changed": True}


def install_claude_skill(
    *,
    dst_dir: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Copy bundled skills (deep-research + gpt2agent) into ``~/.claude/skills/``.

    The deep-research skill calls gpt2agent's ConversationClient directly
    (bypasses MCP) so it works even before restarting Claude Code.
    The gpt2agent skill provides full account access instructions and
    pre-approves all 25 MCP tools.
    """
    skills_src = Path(__file__).parent / "skills"
    target_dir = dst_dir or Path.home() / ".claude" / "skills"

    results = []
    for name in ("deep-research", "gpt2agent"):
        src = skills_src / name
        if not src.exists():
            _warn(f"skill bundle '{name}' not found in package — skipped")
            continue
        results.append(_install_one_skill(name, src, target_dir, dry_run=dry_run))

    if not results:
        return {"path": None, "skipped": True}

    return results[-1]


# ── auto-detect ────────────────────────────────────────────────────────────


def detect_clients() -> list[str]:
    """Return clients whose config locations are present on disk."""
    detected = []
    if (Path.home() / ".claude.json").exists() or (Path.home() / ".claude").exists():
        detected.append("claude-code")
    if (Path.home() / ".codex").exists():
        detected.append("codex")
    for name, (_installer, detect) in _EXTRA_HOSTS.items():
        if detect().exists():
            detected.append(name)
    return detected


# All client names install supports (for --client choices and docs).
SUPPORTED_CLIENTS = ["claude-code", "codex", *_EXTRA_HOSTS.keys()]


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
            elif target in _EXTRA_HOSTS:
                _EXTRA_HOSTS[target][0](dry_run=dry_run)
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
