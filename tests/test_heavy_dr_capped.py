"""Heavy Deep Research pre-flight cap + fail-loud terminal tests — issue #70.

Frame-driven, fully offline (``sse_mod.AsyncSession`` and
``sse_mod.SentinelGate`` stubbed exactly like tests/test_heavy_dr_parser.py).

Covers:

* (A) ``deep_research_heavy`` must consult the ``conversation/init``
  bookkeeping state for the requested model's ``model_limits`` lane (the
  same mechanism as ``_check_model_cap``). A capped model must raise
  ``UsageLimitError`` BEFORE the streaming ``AsyncSession.post`` fires.
* (B) A stream that closes having produced no report text and no done
  event must raise ``RuntimeError("... no report content ...")`` instead
  of silently returning — same guarantee when the phase-2 poll delivers
  an empty terminal event.
* (C) A ``server_ste_metadata`` frame reporting a cheaper ``model_slug``
  than requested is a silent downgrade — raise ``UsageLimitError`` naming
  both slugs, at the moment the metadata frame arrives. ``i-mini-m``
  (the documented orchestration echo), the requested slug itself, and
  other ``*-pro`` tier slugs must NOT trip the check.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from gpt2agent.backend import UsageLimitError


_DISPATCH_TEXT = (
    '{"path": "/Deep Research App/implicit_link::'
    'connector_openai_deep_research/start", "args": {"query": "test"}}'
)
_REAL_REPORT = "# Heavy DR Report\n\nThe answer is 42.\n\n## Section\n\nDetails."


def _envelope(msg_id: str, *, role: str = "assistant", recipient: str = "all",
              parts: list[str] | None = None, status: str = "in_progress",
              c: int = 1, **extra: Any) -> str:
    return "data: " + json.dumps(
        {
            "v": {
                "message": {
                    "id": msg_id,
                    "author": {"role": role},
                    "recipient": recipient,
                    "content": {
                        "content_type": "text",
                        "parts": parts if parts is not None else [""],
                    },
                    "status": status,
                    "metadata": {},
                }
            },
            "c": c,
            **extra,
        }
    )


def _ste_metadata_frame(slug: str) -> str:
    return "data: " + json.dumps(
        {"type": "server_ste_metadata", "metadata": {"model_slug": slug}}
    )


_REPORT_APPEND = "data: " + json.dumps(
    {"p": "/message/content/parts/0", "o": "append", "v": _REAL_REPORT}
)
_STATUS_FINISHED = "data: " + json.dumps(
    {"p": "/message/status", "o": "replace", "v": "finished_successfully"}
)


# Happy-path stream, same shape as test_heavy_dr_parser._FRAMES:
# dispatch envelope suppressed -> api_tool envelope -> tool response ->
# report envelope -> append patch -> status flip -> [DONE].
_FRAMES = [
    _envelope(
        "msg-dispatch", parts=[_DISPATCH_TEXT],
        status="finished_successfully", c=1,
    ),
    _envelope(
        "msg-tool", recipient="api_tool_chatgpt_deep_research",
        parts=["call payload"], status="in_progress", c=2,
    ),
    _envelope(
        "msg-toolresp", role="tool", parts=['{"sources": []}'],
        status="finished_successfully", c=3,
    ),
    _envelope("msg-report", parts=[""], status="in_progress", c=4),
    _REPORT_APPEND,
    _STATUS_FINISHED,
    "data: [DONE]",
]


# ``conversation/init`` bodies for the quota/model-cap pre-flight probes.
# limits_progress carries only the generic ``deep_research`` lane with
# plenty remaining so the heavy-quota probe (``deep_research_*`` features)
# does not fire first.
_INIT_OK = {
    "limits_progress": [{"feature_name": "deep_research", "remaining": 100}],
}
_INIT_CAPPED = {
    "default_model_slug": "gpt-5-6-thinking",
    "model_limits": [
        {"model_slug": "gpt-6-pro", "resets_after": "2999-01-01T00:00:00Z"}
    ],
    "limits_progress": [{"feature_name": "deep_research", "remaining": 100}],
}


class _FakeResp:
    status_code = 200

    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    async def aiter_lines(self):
        for ln in self._lines:
            yield ln


class _InitBackend:
    """Backend stand-in whose ``_session.post`` answers conversation/init.

    Unlike ``_FakeBackend`` in test_heavy_dr_parser (``_session`` is just a
    headers bag), the quota guard probes ``_limits()`` BEFORE streaming, so
    ``_session.post`` must serve the init JSON — same trick as
    ``_CapBackend`` in test_sim.py.
    """

    def __init__(self, init: dict | None) -> None:
        self._init = init

    def _reload_token_if_stale(self) -> None:
        pass

    def _token(self) -> str:
        return "tok"

    class _Sess:
        headers: dict = {"User-Agent": "test-agent"}

        def __init__(self, outer: "_InitBackend") -> None:
            self._o = outer

        def post(self, url: str, **kw: Any):
            outer = self._o

            class _R:
                status_code = 200

                def json(self):
                    return outer._init

            return _R()

    @property
    def _session(self):
        return _InitBackend._Sess(self)


class _FakeSentinel:
    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    async def get_tokens(self) -> dict[str, str]:
        return {"chat-requirements": "stub", "proof": "", "turnstile": ""}


async def _empty_done_poll(self, conv_id, **kwargs):
    """Phase-2 stand-in: poll timed out with no report text."""
    yield {
        "type": "done",
        "text": "",
        "content_references": [],
        "search_result_groups": [],
        "terminated_abnormally": True,
        "timeout": True,
    }


def _collect_heavy_dr(
    monkeypatch: pytest.MonkeyPatch,
    frames: list[str],
    backend: Any = None,
    poll: Any = None,
) -> tuple[list[dict], BaseException | None, type]:
    """Drive ``deep_research_heavy`` over canned SSE frames, zero network.

    Returns ``(events, error, SessionClass)`` — events yielded before an
    error, the error itself (``None`` on clean completion), and the fake
    session class whose ``posts`` counter tracks streaming POSTs.
    """
    from gpt2agent import sse as sse_mod

    class _FrameSession:
        posts = 0

        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        async def __aenter__(self) -> "_FrameSession":
            return self

        async def __aexit__(self, *exc: Any) -> None:
            return None

        async def post(self, *_: Any, **__: Any) -> _FakeResp:
            type(self).posts += 1
            return _FakeResp(frames)

    monkeypatch.setattr(sse_mod, "AsyncSession", _FrameSession)
    monkeypatch.setattr(sse_mod, "SentinelGate", _FakeSentinel)
    if poll is not None:
        monkeypatch.setattr(
            sse_mod.ConversationClient, "_poll_dr_completion", poll
        )

    client = sse_mod.ConversationClient(  # type: ignore[arg-type]
        backend or _InitBackend(_INIT_OK)
    )

    async def _go() -> tuple[list[dict], BaseException | None]:
        out: list[dict] = []
        err: BaseException | None = None
        try:
            async for ev in client.deep_research_heavy("test query"):
                out.append(ev)
        except Exception as exc:  # noqa: BLE001 - surfaced to assertions
            err = exc
        return out, err

    events, err = asyncio.run(_go())
    return events, err, _FrameSession


# ── (A) pre-flight model cap ─────────────────────────────────────────────


def test_model_cap_preflight_raises_before_streaming_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """model_limits capping gpt-6-pro must abort before the SSE POST."""
    events, err, session = _collect_heavy_dr(
        monkeypatch, _FRAMES, backend=_InitBackend(_INIT_CAPPED)
    )

    assert isinstance(err, UsageLimitError), (
        f"expected UsageLimitError from the model_limits pre-flight, "
        f"got err={err!r} events={events}"
    )
    assert "gpt-6-pro" in str(err)
    assert session.posts == 0, (
        "the streaming POST must not fire once the model cap is known"
    )


def test_uncapped_init_streams_report(monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: no model_limits entry -> the stream runs and completes."""
    events, err, session = _collect_heavy_dr(monkeypatch, _FRAMES)

    assert err is None, f"unexpected error: {err!r}"
    assert session.posts == 1
    dones = [e for e in events if e.get("type") == "done"]
    assert len(dones) == 1
    assert dones[0]["text"] == _REAL_REPORT


# ── (B) fail-loud empty terminal ─────────────────────────────────────────


def test_empty_terminal_stream_raises_no_report_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stream closes with only an empty dispatch envelope -> loud failure.

    The envelope carries a top-level conversation_id but never invokes the
    tool, so the phase-2 poll is skipped; with no report text and no done
    the call must raise instead of returning nothing.
    """
    frames = [
        _envelope(
            "msg-empty-dispatch", parts=[""],
            status="finished_successfully", c=1,
            conversation_id="conv-empty",
        ),
        "data: [DONE]",
    ]
    events, err, _ = _collect_heavy_dr(monkeypatch, frames)

    assert isinstance(err, RuntimeError), (
        f"expected RuntimeError on empty terminal stream, "
        f"got err={err!r} events={events}"
    )
    assert "no report content" in str(err)
    assert all(e.get("type") != "done" for e in events)


def test_empty_polled_terminal_raises_no_report_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase-2 poll delivering an empty timeout done -> loud failure.

    tool_invoked + conversation_id route into the phase-2 poll; its
    terminal ``done`` carries no report text and must be converted to a
    RuntimeError, never yielded to the caller.
    """
    frames = [
        "data: "
        + json.dumps(
            {
                "type": "resume_conversation_token",
                "token": "t",
                "conversation_id": "conv-x",
            }
        ),
        _envelope(
            "msg-tool", recipient="api_tool_chatgpt_deep_research",
            parts=["call payload"], status="in_progress", c=2,
            conversation_id="conv-x",
        ),
        "data: [DONE]",
    ]
    events, err, _ = _collect_heavy_dr(
        monkeypatch, frames, poll=_empty_done_poll
    )

    assert isinstance(err, RuntimeError), (
        f"expected RuntimeError on empty polled terminal, "
        f"got err={err!r} events={events}"
    )
    assert "no report content" in str(err)
    assert all(e.get("type") != "done" for e in events)


# ── (C) downgrade-as-error ───────────────────────────────────────────────


def test_ste_metadata_downgrade_raises_usage_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """server_ste_metadata model_slug cheaper than requested -> UsageLimitError.

    Raised when the metadata frame arrives, so no ``done`` is ever yielded.
    """
    frames = [
        _ste_metadata_frame("gpt-5-mini"),
        _envelope("msg-report", parts=[""], status="in_progress", c=4),
        _REPORT_APPEND,
        _STATUS_FINISHED,
        "data: [DONE]",
    ]
    events, err, _ = _collect_heavy_dr(monkeypatch, frames)

    assert isinstance(err, UsageLimitError), (
        f"expected UsageLimitError on silent model downgrade, "
        f"got err={err!r} events={events}"
    )
    assert "downgrad" in str(err).lower()
    assert "gpt-5-mini" in str(err)
    assert "gpt-6-pro" in str(err)
    assert all(e.get("type") != "done" for e in events)


@pytest.mark.parametrize(
    "slug",
    [
        "i-mini-m",     # documented orchestration-layer echo, not the model
        "gpt-6-pro",    # == the requested model
        "gpt-5-5-pro",  # a *-pro tier slug — conservatively not a downgrade
    ],
)
def test_ste_metadata_non_downgrade_slug_passes(
    monkeypatch: pytest.MonkeyPatch, slug: str
) -> None:
    """Slugs that are NOT downgrades must let the stream complete."""
    frames = _FRAMES[:3] + [_ste_metadata_frame(slug)] + _FRAMES[3:]
    events, err, _ = _collect_heavy_dr(monkeypatch, frames)

    assert err is None, f"slug {slug!r} must not fail the stream: {err!r}"
    dones = [e for e in events if e.get("type") == "done"]
    assert len(dones) == 1
    assert dones[0]["text"] == _REAL_REPORT


@pytest.mark.parametrize("valid_connector", [True, False])
def test_outer_chat_slug_does_not_reject_verified_async_research(
    monkeypatch: pytest.MonkeyPatch, valid_connector: bool
) -> None:
    """Recorded successful DR uses gpt-5-6-instant as its outer Chat model."""
    from copy import deepcopy
    from gpt2agent import sse as sse_mod
    from tests.test_heavy_dr_parser import _generated_live_detail

    detail = _generated_live_detail(report=_REAL_REPORT)
    startup = deepcopy(detail["mapping"]["generated-tool-node"]["message"])
    if not valid_connector:
        startup["metadata"]["chatgpt_sdk"]["attribution_id"] = "unrelated_connector"
    frames = [
        'data: ' + json.dumps({
            'v': {'message': startup},
            'conversation_id': 'generated-conversation',
        }),
        'data: ' + json.dumps({
            'type': 'server_ste_metadata',
            'metadata': {
                'model_slug': 'gpt-5-6-instant',
                'tool_name': 'CodeModeTool',
                'tool_invoked': True,
            },
        }),
        'data: [DONE]',
    ]

    class Backend(_InitBackend):
        def get(self, path: str, **kwargs: Any) -> dict:
            return detail

    async def no_sleep(*args: Any) -> None:
        pass

    monkeypatch.setattr(sse_mod.asyncio, 'sleep', no_sleep)
    events, err, _ = _collect_heavy_dr(monkeypatch, frames, backend=Backend(_INIT_OK))
    if valid_connector:
        assert err is None
        done = [e for e in events if e.get('type') == 'done']
        expected, _ = sse_mod._dr_report_from_widget_state(detail)
        assert expected
        assert len(done) == 1 and done[0]['text'] == expected
    else:
        assert isinstance(err, UsageLimitError)
        assert not any(e.get('type') == 'done' for e in events)
