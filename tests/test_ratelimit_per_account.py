"""Per-account rate-limit state + ``gpt2agent ratelimit`` CLI — issue #70.

Multi-account hosts select the ChatGPT login via ``CODEX_HOME``; account A
exhausting its conversation budget says nothing about account B. With no
explicit ``state_path`` and no ``GPT2AGENT_RATELIMIT_STATE`` override,
``RateLimiter`` must therefore derive its state filename from
``CODEX_HOME`` — ``ratelimit-state-<acct>.json`` beside the default
``ratelimit-state.json`` (unchanged back-compat path when CODEX_HOME is
unset). ``get_limiter``/``reset_limiter`` singleton coherence follows the
same derivation.

Every test monkeypatches ``ratelimit._STATE_PATH`` into ``tmp_path`` (same
trick as tests/test_sim.py:381 patching ``sim_mod._STATE_PATH``) so the
real ``~/.gpt2agent`` is never touched, and re-enables the limiter by
removing the conftest's ``GPT2AGENT_RATELIMIT_OFF``.

Also covers the local-state-only ``gpt2agent ratelimit --json`` CLI:
no network, no ChatGPT token required.
"""

from __future__ import annotations

import json
import sys

import pytest

from gpt2agent import ratelimit as ratelimit_mod
from gpt2agent.ratelimit import (
    LocalRateLimitError,
    RateLimiter,
    get_limiter,
    reset_limiter,
)


_CFG = {
    "rate_limit": {
        "enabled": True,
        "max_per_window": 1,
        "min_interval_s": 0.0,
        "window_s": 3600.0,
        "max_wait_s": 5.0,
    }
}


@pytest.fixture
def rl_tmp(tmp_path, monkeypatch):
    """Hermetic rate-limit state: ``_STATE_PATH`` under tmp, limiter on."""
    monkeypatch.setattr(
        ratelimit_mod, "_STATE_PATH", tmp_path / "ratelimit-state.json"
    )
    monkeypatch.delenv("GPT2AGENT_RATELIMIT_OFF", raising=False)
    monkeypatch.delenv("GPT2AGENT_RATELIMIT_STATE", raising=False)
    reset_limiter()
    yield tmp_path
    reset_limiter()


# ── (D) per-account state derivation ─────────────────────────────────────


def test_state_path_derives_per_codex_home(rl_tmp, monkeypatch) -> None:
    """Different CODEX_HOME -> different ratelimit-state-*.json files."""
    monkeypatch.setenv("CODEX_HOME", str(rl_tmp / "acct-a"))
    lim_a = RateLimiter()
    lim_a2 = RateLimiter()
    monkeypatch.setenv("CODEX_HOME", str(rl_tmp / "acct-b"))
    lim_b = RateLimiter()

    # Deterministic within an account, distinct across accounts.
    assert lim_a2.state_path == lim_a.state_path
    assert lim_a.state_path != lim_b.state_path
    for path in (lim_a.state_path, lim_b.state_path):
        assert path.parent == rl_tmp
        assert path.name.startswith("ratelimit-state-")
        assert path.name.endswith(".json")
        assert path.name != "ratelimit-state.json"


def test_state_path_back_compat_without_codex_home(
    rl_tmp, monkeypatch
) -> None:
    """CODEX_HOME unset -> the historical single-tenant filename."""
    monkeypatch.delenv("CODEX_HOME", raising=False)
    lim = RateLimiter()
    assert lim.state_path == rl_tmp / "ratelimit-state.json"


def test_conversation_lane_exhaustion_isolated_per_account(
    rl_tmp, monkeypatch
) -> None:
    """Account A's exhausted window must not refuse account B."""
    monkeypatch.setenv("CODEX_HOME", str(rl_tmp / "acct-a"))
    lim_a = RateLimiter(_CFG)
    lim_a._reserve("conv_requests", "last_conv", 0.0, windowed=True)
    with pytest.raises(LocalRateLimitError):
        lim_a._reserve("conv_requests", "last_conv", 0.0, windowed=True)

    monkeypatch.setenv("CODEX_HOME", str(rl_tmp / "acct-b"))
    lim_b = RateLimiter(_CFG)
    # Account B's budget is untouched by account A's exhaustion.
    lim_b._reserve("conv_requests", "last_conv", 0.0, windowed=True)


def test_get_limiter_singleton_tracks_codex_home(rl_tmp, monkeypatch) -> None:
    """reset_limiter() + get_limiter() must re-derive per CODEX_HOME."""
    try:
        monkeypatch.setenv("CODEX_HOME", str(rl_tmp / "acct-a"))
        reset_limiter()
        path_a = get_limiter().state_path
        assert path_a == RateLimiter().state_path

        monkeypatch.setenv("CODEX_HOME", str(rl_tmp / "acct-b"))
        reset_limiter()
        path_b = get_limiter().state_path
        assert path_b == RateLimiter().state_path
        assert path_a != path_b
    finally:
        reset_limiter()


# ── (E) `gpt2agent ratelimit --json` ─────────────────────────────────────


def test_ratelimit_cli_json(rl_tmp, monkeypatch, capsys) -> None:
    """Local-state-only CLI: returns normally, prints a JSON budget dict."""
    from gpt2agent import server

    monkeypatch.setenv("CODEX_HOME", str(rl_tmp / "acct-cli"))
    reset_limiter()
    monkeypatch.setattr(sys, "argv", ["gpt2agent", "ratelimit", "--json"])
    try:
        server.main()  # exit 0 — no SystemExit, no exception, no network
    finally:
        reset_limiter()

    out = json.loads(capsys.readouterr().out)
    assert isinstance(out, dict)
    for key in ("lane", "window_remaining_s", "wait_s"):
        assert key in out, f"missing {key!r} in ratelimit --json output: {out}"
