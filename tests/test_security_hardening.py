"""Unit tests for the 2026-06-18 audit hardening — no network.

Covers:
  * `_log_redact.redact_error` — bare Bearer, named token fields, cookies, query tokens.
  * `server._http_bind_decision` — loopback ok / non-loopback refused without opt-in.
  * `sse._dr_report_from_widget_state` — author-role gate, prefix-must-start,
    and in-progress drafts rejected (DR-report spoofing/premature-done guards).
  * `_poll_dr_completion` requests the hidden-widget-state query flags.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from gpt2agent import sse as sse_mod
from gpt2agent._log_redact import redact_error
from gpt2agent.server import _http_bind_decision


# --------------------------------------------------------------------------- #
#  _log_redact.redact_error
# --------------------------------------------------------------------------- #


def test_redact_bare_bearer() -> None:
    out = redact_error("upstream said: Bearer eyJabc.DEF-123_xyz tail", max_len=500)
    assert "eyJabc.DEF-123_xyz" not in out
    assert "Bearer <REDACTED>" in out


def test_redact_named_token_fields() -> None:
    out = redact_error('{"tokens": {"access_token": "s3cr3t-value"}}', max_len=500)
    assert "s3cr3t-value" not in out
    assert "<REDACTED>" in out


def test_redact_session_cookie() -> None:
    out = redact_error("Cookie: __Secure-next-auth.session-token=a.b.c; Path=/", max_len=500)
    assert "a.b.c" not in out


def test_redact_query_token_keeps_other_params() -> None:
    out = redact_error("GET /download?access_token=zzz999&file=report.md", max_len=500)
    assert "zzz999" not in out
    assert "file=report.md" in out  # non-secret params preserved


def test_redact_quoted_authorization_header() -> None:
    out = redact_error('{"Authorization": "Bearer eyJsecret"}', max_len=500)
    assert "eyJsecret" not in out


def test_redact_truncates_long_body() -> None:
    assert redact_error("A" * 1000, max_len=50).endswith("...[truncated]")


# --------------------------------------------------------------------------- #
#  server._http_bind_decision
# --------------------------------------------------------------------------- #


def test_bind_loopback_is_ok() -> None:
    assert _http_bind_decision("127.0.0.1", False) == "ok-loopback"
    assert _http_bind_decision("localhost", False) == "ok-loopback"
    assert _http_bind_decision("::1", False) == "ok-loopback"


def test_bind_non_loopback_refused_without_optin() -> None:
    assert _http_bind_decision("0.0.0.0", False) == "refuse"
    assert _http_bind_decision("192.168.1.5", False) == "refuse"


def test_bind_non_loopback_allowed_with_optin() -> None:
    assert _http_bind_decision("0.0.0.0", True) == "ok-remote"


# --------------------------------------------------------------------------- #
#  sse._dr_report_from_widget_state hardening
# --------------------------------------------------------------------------- #


def _carrier(role: str, *, report_status: str, widget_status: str, body: str, lead: str = "") -> dict:
    state = {
        "status": widget_status,
        "report_message": {
            "content": {"parts": [body]},
            "status": report_status,
            "metadata": {"content_references": [{"items": []}]},
        },
    }
    part = lead + sse_mod._WIDGET_STATE_TEXT_PREFIX + json.dumps(state)
    return {
        "mapping": {
            "n": {
                "message": {
                    "author": {"role": role},
                    "content": {"content_type": "text", "parts": [part]},
                }
            }
        }
    }


def test_widget_tool_completed_accepted() -> None:
    detail = _carrier("tool", report_status="finished_successfully", widget_status="completed", body="# Real report")
    text, refs = sse_mod._dr_report_from_widget_state(detail)
    assert text == "# Real report"
    assert refs


def test_widget_user_role_spoof_rejected() -> None:
    """A user-authored message containing the widget prefix must NOT be parsed as the report."""
    detail = _carrier("user", report_status="finished_successfully", widget_status="completed", body="# SPOOFED")
    text, refs = sse_mod._dr_report_from_widget_state(detail)
    assert text == ""
    assert refs == []


def test_widget_in_progress_draft_rejected() -> None:
    detail = _carrier("tool", report_status="in_progress", widget_status="running", body="half-written draft")
    text, _ = sse_mod._dr_report_from_widget_state(detail)
    assert text == ""


def test_widget_prefix_must_start_the_part() -> None:
    """Prefix embedded mid-string (e.g. inside a pasted blob) must not match."""
    detail = _carrier(
        "tool", report_status="finished_successfully", widget_status="completed",
        body="# x", lead="here is some chatter: ",
    )
    text, _ = sse_mod._dr_report_from_widget_state(detail)
    assert text == ""


# --------------------------------------------------------------------------- #
#  _poll_dr_completion requests the widget-state query flags (cx PR#9 test gap)
# --------------------------------------------------------------------------- #


def test_poll_requests_widget_state_query_flags() -> None:
    detail = _carrier("tool", report_status="finished_successfully", widget_status="completed", body="# R")
    seen: dict[str, str] = {}

    class _RecordingBackend:
        class _Sess:
            headers: dict[str, str] = {"User-Agent": "test"}

        _session = _Sess()

        def _reload_token_if_stale(self) -> None:
            pass

        def get(self, path: str, *a: Any, **k: Any) -> dict:
            seen["path"] = path
            return detail

    client = sse_mod.ConversationClient(_RecordingBackend())  # type: ignore[arg-type]

    async def _go() -> None:
        async for _ev in client._poll_dr_completion("cid", interval=0, max_wait=1):
            break

    asyncio.run(_go())
    assert "include_visually_hidden_messages=true" in seen["path"]
    assert "include_widget_state=true" in seen["path"]
