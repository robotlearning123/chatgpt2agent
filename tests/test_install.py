"""Tests for the ``openai-mcp install`` subcommand.

Verifies the Claude Code and Codex registration logic against synthetic
config files in ``tmp_path``. Never touches the real ``~/.claude.json`` or
``~/.codex/config.toml``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openai_mcp.install import (
    _replace_or_append_toml_section,
    detect_clients,
    install_claude_code,
    install_claude_skill,
    install_codex,
)


# ── Claude Code ────────────────────────────────────────────────────────────


def test_claude_new_config(tmp_path: Path) -> None:
    cfg = tmp_path / "claude.json"
    result = install_claude_code(config_path=cfg)
    assert result["changed"] is True
    assert result["backup"] is None  # no prior file → no backup

    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["openai"]["type"] == "stdio"
    assert data["mcpServers"]["openai"]["command"] == "openai-mcp"
    assert data["mcpServers"]["openai"]["args"] == ["run", "--stdio"]


def test_claude_preserves_other_keys(tmp_path: Path) -> None:
    cfg = tmp_path / "claude.json"
    cfg.write_text(
        json.dumps(
            {
                "numStartups": 42,
                "tipsHistory": {"x": 1},
                "mcpServers": {"existing": {"type": "stdio", "command": "other"}},
            }
        )
    )
    install_claude_code(config_path=cfg)

    data = json.loads(cfg.read_text())
    assert data["numStartups"] == 42
    assert data["tipsHistory"] == {"x": 1}
    assert data["mcpServers"]["existing"]["command"] == "other"
    assert data["mcpServers"]["openai"]["command"] == "openai-mcp"


def test_claude_writes_backup(tmp_path: Path) -> None:
    cfg = tmp_path / "claude.json"
    cfg.write_text('{"original": true, "mcpServers": {}}')
    result = install_claude_code(config_path=cfg)

    assert result["backup"] is not None
    assert result["backup"].exists()
    assert '"original": true' in result["backup"].read_text()


def test_claude_idempotent(tmp_path: Path) -> None:
    cfg = tmp_path / "claude.json"
    install_claude_code(config_path=cfg)
    snap = cfg.read_text()
    result = install_claude_code(config_path=cfg)
    assert result["changed"] is False
    assert cfg.read_text() == snap


def test_claude_http_transport(tmp_path: Path) -> None:
    cfg = tmp_path / "claude.json"
    install_claude_code(config_path=cfg, transport="http", http_port=9001)
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["openai"]["type"] == "url"
    assert data["mcpServers"]["openai"]["url"] == "http://localhost:9001/mcp"


def test_claude_rejects_broken_json(tmp_path: Path) -> None:
    cfg = tmp_path / "claude.json"
    cfg.write_text("{not valid json")
    with pytest.raises(RuntimeError, match="not valid JSON"):
        install_claude_code(config_path=cfg)


def test_claude_dry_run_no_write(tmp_path: Path) -> None:
    cfg = tmp_path / "claude.json"
    cfg.write_text('{"existing": true}')
    install_claude_code(config_path=cfg, dry_run=True)
    assert cfg.read_text() == '{"existing": true}'


# ── Codex ──────────────────────────────────────────────────────────────────


def test_codex_new_config(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    install_codex(config_path=cfg)
    text = cfg.read_text()
    assert "[mcp_servers.openai]" in text
    assert 'command = "openai-mcp"' in text
    assert 'args = ["run", "--stdio"]' in text


def test_codex_preserves_existing_sections(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        'approval_policy = "never"\n'
        'model = "gpt-5.5"\n'
        "\n"
        "[agents]\n"
        "max_depth = 2\n"
        "\n"
        "[agents.explorer]\n"
        'config_file = "agents/explorer.toml"\n'
    )
    install_codex(config_path=cfg)
    text = cfg.read_text()
    assert 'approval_policy = "never"' in text
    assert 'model = "gpt-5.5"' in text
    assert "[agents]" in text
    assert "max_depth = 2" in text
    assert "[agents.explorer]" in text
    assert 'config_file = "agents/explorer.toml"' in text
    assert "[mcp_servers.openai]" in text


def test_codex_replaces_existing_mcp_section(tmp_path: Path) -> None:
    """Re-installing must replace the stale [mcp_servers.openai] body, not duplicate."""
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        "[mcp_servers.openai]\n"
        'command = "OLD_COMMAND"\n'
        'args = ["old", "args"]\n'
        "\n"
        "[other]\n"
        "key = 1\n"
    )
    install_codex(config_path=cfg)
    text = cfg.read_text()
    assert "OLD_COMMAND" not in text
    assert text.count("[mcp_servers.openai]") == 1
    assert "[other]" in text
    assert "key = 1" in text


def test_codex_idempotent(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    install_codex(config_path=cfg)
    snap = cfg.read_text()
    result = install_codex(config_path=cfg)
    assert result["changed"] is False
    assert cfg.read_text() == snap


def test_codex_dry_run_no_write(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('approval_policy = "never"\n')
    install_codex(config_path=cfg, dry_run=True)
    assert cfg.read_text() == 'approval_policy = "never"\n'


# ── Skill bundle ───────────────────────────────────────────────────────────


def test_skill_install(tmp_path: Path) -> None:
    """Bundled skill copies into a Claude Code skills directory."""
    skills_root = tmp_path / "claude" / "skills"
    result = install_claude_skill(dst_dir=skills_root)
    # If skill bundle missing from package, test is informational only.
    if result.get("skipped"):
        pytest.skip("skill bundle not present in package")
    dst = skills_root / "deep-research"
    assert dst.exists()
    assert (dst / "SKILL.md").exists()
    assert (dst / "bin" / "run.sh").exists()


def test_skill_backup_on_overwrite(tmp_path: Path) -> None:
    skills_root = tmp_path / "claude" / "skills"
    first = install_claude_skill(dst_dir=skills_root)
    if first.get("skipped"):
        pytest.skip("skill bundle not present in package")
    # Touch a sentinel file to verify it lands in the backup.
    sentinel = skills_root / "deep-research" / "USER_OVERRIDE.txt"
    sentinel.write_text("user-edited")
    second = install_claude_skill(dst_dir=skills_root)
    assert second["backup"] is not None
    assert (second["backup"] / "USER_OVERRIDE.txt").exists()


# ── TOML section editor ────────────────────────────────────────────────────


def test_replace_toml_section_append_when_absent() -> None:
    out = _replace_or_append_toml_section(
        "key = 1\n",
        "mcp_servers.x",
        ["command = \"foo\""],
    )
    assert "key = 1" in out
    assert "[mcp_servers.x]" in out
    assert 'command = "foo"' in out


def test_replace_toml_section_replaces_body() -> None:
    src = (
        "[mcp_servers.x]\n"
        'command = "old"\n'
        'args = ["a"]\n'
        "\n"
        "[other]\n"
        "k = 2\n"
    )
    out = _replace_or_append_toml_section(
        src, "mcp_servers.x", ['command = "new"', 'args = ["b"]']
    )
    assert "old" not in out
    assert '[other]' in out
    assert 'k = 2' in out
    assert out.count("[mcp_servers.x]") == 1


# ── detect ─────────────────────────────────────────────────────────────────


def test_detect_clients_with_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert detect_clients() == []

    (tmp_path / ".claude").mkdir()
    assert "claude-code" in detect_clients()

    (tmp_path / ".codex").mkdir()
    detected = detect_clients()
    assert "claude-code" in detected
    assert "codex" in detected
