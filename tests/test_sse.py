"""Live SSE roundtrip: ask model to reply with PONG, verify stream parses.

Live tests are skipped by default to keep `pytest tests/` offline-safe.
Opt in with ``SKIP_LIVE=0`` (and, for the heavy DR variant, ``SKIP_HEAVY_DR=0``).
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

_SKIP_LIVE = os.environ.get("SKIP_LIVE", "1") == "1"
_SKIP_HEAVY_DR = os.environ.get("SKIP_HEAVY_DR", "1") == "1"


@pytest.mark.skipif(
    not (Path.home() / ".codex" / "auth.json").exists(),
    reason="requires ~/.codex/auth.json",
)
@pytest.mark.skipif(_SKIP_LIVE, reason="SKIP_LIVE=1 (default); set SKIP_LIVE=0 to run")
def test_sse_pong():
    from openai_mcp.backend import BackendClient
    from openai_mcp.sse import ConversationClient

    conv = ConversationClient(BackendClient())
    out = asyncio.run(
        conv.complete(
            "gpt-5-3",
            [{"role": "user", "content": "Reply with exactly: PONG"}],
        )
    )
    assert "pong" in out.lower(), f"no PONG in response: {out!r}"


@pytest.mark.skipif(
    not (Path.home() / ".codex" / "auth.json").exists(),
    reason="requires ~/.codex/auth.json",
)
@pytest.mark.skipif(
    _SKIP_LIVE or _SKIP_HEAVY_DR,
    reason="heavy DR skipped by default; set SKIP_LIVE=0 SKIP_HEAVY_DR=0 to run",
)
def test_sse_deep_research_heavy():
    """Live deep-research probe — skipped by default (slow + costly)."""
    from openai_mcp.backend import BackendClient
    from openai_mcp.sse import ConversationClient

    conv = ConversationClient(BackendClient())
    out = asyncio.run(
        conv.complete(
            "research",
            [{"role": "user", "content": "Summarize: what is 2+2? One sentence."}],
        )
    )
    assert out and out.strip(), "empty DR response"
