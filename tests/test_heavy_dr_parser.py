"""Heavy Deep Research parser tests — no network.

Validates the P0 #1 fix: when the first assistant envelope is the connector-
dispatch payload (`{"path": ".../connector_openai_deep_research/start", ...}`),
its ``finished_successfully`` status must NOT trigger ``_emit_done``. The real
report arrives in a later envelope and that one's done is the one we want.

Also covers the temp-chat regression — DR payloads must not set
``history_and_training_disabled: True`` (ChatGPT refuses DR in temp chats).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest


_DISPATCH_TEXT = (
    '{"path": "/Deep Research App/implicit_link::'
    'connector_openai_deep_research/start", "args": {"query": "test"}}'
)
_REAL_REPORT = "# Heavy DR Report\n\nThe answer is 42.\n\n## Section\n\nDetails."


_FRAMES = [
    # 1. Connector-dispatch envelope — text is the connector JSON, status
    #    reaches finished_successfully almost immediately. MUST be suppressed.
    "data: "
    + json.dumps(
        {
            "v": {
                "message": {
                    "id": "msg-dispatch",
                    "author": {"role": "assistant"},
                    "recipient": "all",
                    "content": {
                        "content_type": "text",
                        "parts": [_DISPATCH_TEXT],
                    },
                    "status": "finished_successfully",
                    "metadata": {},
                }
            },
            "c": 1,
        }
    ),
    # 2. api_tool_* envelope marks the connector as invoked.
    "data: "
    + json.dumps(
        {
            "v": {
                "message": {
                    "id": "msg-tool",
                    "author": {"role": "assistant"},
                    "recipient": "api_tool_chatgpt_deep_research",
                    "content": {"content_type": "text", "parts": ["call payload"]},
                    "status": "in_progress",
                    "metadata": {},
                }
            },
            "c": 2,
        }
    ),
    # 3. tool-response (role=tool, recipient=all) — not a done trigger.
    "data: "
    + json.dumps(
        {
            "v": {
                "message": {
                    "id": "msg-toolresp",
                    "author": {"role": "tool"},
                    "recipient": "all",
                    "content": {"content_type": "text", "parts": ['{"sources": []}']},
                    "status": "finished_successfully",
                    "metadata": {},
                }
            },
            "c": 3,
        }
    ),
    # 4. Fresh assistant envelope — the REAL report (in_progress, empty text).
    "data: "
    + json.dumps(
        {
            "v": {
                "message": {
                    "id": "msg-report",
                    "author": {"role": "assistant"},
                    "recipient": "all",
                    "content": {"content_type": "text", "parts": [""]},
                    "status": "in_progress",
                    "metadata": {},
                }
            },
            "c": 4,
        }
    ),
    # 5. Streamed report content via path-scoped append patch.
    "data: "
    + json.dumps(
        {
            "p": "/message/content/parts/0",
            "o": "append",
            "v": _REAL_REPORT,
        }
    ),
    # 6. Status flips to finished_successfully — the REAL done.
    "data: "
    + json.dumps({"p": "/message/status", "o": "replace", "v": "finished_successfully"}),
    "data: [DONE]",
]


class _FakeResp:
    status_code = 200

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    async def aiter_lines(self):
        for ln in self._lines:
            yield ln


class _FakeSession:
    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def post(self, *_: Any, **__: Any) -> _FakeResp:
        return _FakeResp(_FRAMES)


class _FakeBackend:
    class _Sess:
        headers: dict[str, str] = {"User-Agent": "test-agent"}

    _session = _Sess()

    def _reload_token_if_stale(self) -> None:  # mirrors BackendClient
        pass

    def post(self, *args: Any, **kwargs: Any) -> dict:
        # Quota probe response — plenty of DR quota left.
        return {
            "limits_progress": [{"feature_name": "deep_research", "remaining": 100}]
        }


class _FakeSentinel:
    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    async def get_tokens(self) -> dict[str, str]:
        return {"chat-requirements": "stub", "proof": "", "turnstile": ""}


def _run_heavy_dr(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    from gpt2agent import sse as sse_mod

    monkeypatch.setattr(sse_mod, "AsyncSession", _FakeSession)
    monkeypatch.setattr(sse_mod, "SentinelGate", _FakeSentinel)

    client = sse_mod.ConversationClient(_FakeBackend())  # type: ignore[arg-type]

    async def _go() -> list[dict]:
        out: list[dict] = []
        async for ev in client.deep_research_heavy("test query"):
            out.append(ev)
        return out

    return asyncio.run(_go())


def test_connector_dispatch_done_suppressed(monkeypatch: pytest.MonkeyPatch) -> None:
    events = _run_heavy_dr(monkeypatch)
    dones = [e for e in events if e.get("type") == "done"]

    # Exactly one done — the dispatch envelope's finished_successfully must
    # have been suppressed.
    assert len(dones) == 1, f"expected 1 done event, got {len(dones)}: {dones}"

    # And it must hold the REAL report, not the dispatch JSON.
    assert dones[0]["text"] == _REAL_REPORT
    assert _DISPATCH_TEXT not in dones[0]["text"]


def test_progress_excludes_dispatch_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Streaming progress events must not surface connector-dispatch JSON."""
    events = _run_heavy_dr(monkeypatch)
    progress_text = "".join(
        e["text"] for e in events if e.get("type") == "progress"
    )
    assert _DISPATCH_TEXT not in progress_text
    assert _REAL_REPORT in progress_text


def test_dr_payloads_disable_temp_chat() -> None:
    """history_and_training_disabled must be False for DR payloads.

    Otherwise ChatGPT rejects with "Research is not currently supported in
    temporary chats" and DR also can't be Phase-2-polled (temp chats aren't
    persisted at /backend-api/conversation/{id}).
    """
    from gpt2agent import sse as sse_mod

    light = sse_mod._build_dr_payload("test query")
    assert light["history_and_training_disabled"] is False, light

    heavy = sse_mod._build_heavy_dr_payload("test query")
    assert heavy["history_and_training_disabled"] is False, heavy


def test_heavy_dr_model_override() -> None:
    """heavy_dr model param overrides the HEAVY_DR_MODEL default."""
    from gpt2agent import sse as sse_mod

    default = sse_mod._build_heavy_dr_payload("q")
    assert default["model"] == sse_mod.HEAVY_DR_MODEL

    overridden = sse_mod._build_heavy_dr_payload("q", model="gpt-5-4-pro")
    assert overridden["model"] == "gpt-5-4-pro"


def test_chat_payload_supports_gizmo_id() -> None:
    """gpt_chat passes gizmo_id into the chat payload (custom GPT routing)."""
    from gpt2agent import sse as sse_mod

    no_gizmo = sse_mod._build_payload(
        "gpt-5-3", [{"role": "user", "content": "hi"}]
    )
    assert "gizmo_id" not in no_gizmo
    assert "conversation_origin" not in no_gizmo

    with_gizmo = sse_mod._build_payload(
        "gpt-5-3",
        [{"role": "user", "content": "hi"}],
        gizmo_id="g-p-test123",
    )
    assert with_gizmo["gizmo_id"] == "g-p-test123"
    assert with_gizmo["conversation_origin"] == {
        "type": "custom_gpt",
        "gizmo_id": "g-p-test123",
    }
