"""Native SSE client for /backend-api/conversation — no proxy required."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import AsyncIterator
from uuid import uuid4

from curl_cffi.requests import AsyncSession

from openai_mcp.backend import BackendClient, _BASE
from openai_mcp.sentinel import SentinelGate  # noqa: F401  (used in stream)

_log = logging.getLogger(__name__)

_CONV_URL = _BASE + "/backend-api/conversation"

# Matches JSON-encoded session-scoped tokens/headers so we can redact them
# from error messages and logs.
_SENSITIVE_KEY_RE = re.compile(
    r'"(Openai-Sentinel-[A-Za-z-]+-Token|Authorization|OAI-[A-Za-z-]+)"\s*:\s*"[^"]*"',
    re.IGNORECASE,
)


def _redact_error(text: str, max_len: int = 200) -> str:
    """Truncate + redact session-scoped tokens before surfacing to the user."""
    if not isinstance(text, str):
        text = str(text)
    cleaned = _SENSITIVE_KEY_RE.sub(r'"\1":"<REDACTED>"', text)
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "...[truncated]"
    return cleaned


def _safe_body(resp: object) -> str:
    try:
        text = getattr(resp, "text", "") or ""
    except Exception:
        return ""
    return _redact_error(text) if text else ""


# /backend-api/f/conversation — the frontend-facing endpoint used by the web app.
# Required for Deep Research heavy path; regular /conversation also works for normal chat.
_F_CONV_URL = _BASE + "/backend-api/f/conversation"

#: Model slug for legacy Deep Research (resolves to i-mini-m / web-search backend)
DR_MODEL = "research"

#: Model slug for heavy Deep Research — gpt-5-5-pro with extended thinking + DR connector
HEAVY_DR_MODEL = "gpt-5-5-pro"

#: System hint for heavy Deep Research (connector identifier from chatgpt.com frontend)
HEAVY_DR_HINT = "connector:connector_openai_deep_research"


def _build_payload(model: str, messages: list[dict]) -> dict:
    return {
        "action": "next",
        "messages": [
            {
                "id": str(uuid4()),
                "author": {"role": m["role"]},
                "content": {"content_type": "text", "parts": [m["content"]]},
            }
            for m in messages
        ],
        "parent_message_id": str(uuid4()),
        "model": model,
        "conversation_mode": {"kind": "primary_assistant"},
        "force_paragen": False,
        "force_rate_limit": False,
        "force_use_sse": True,
        "timezone_offset_min": -480,
        "history_and_training_disabled": True,
        "system_hints": [],
    }


def _build_dr_payload(query: str) -> dict:
    """Build payload for legacy Deep Research: model=research + system_hints=['research'].

    This resolves to i-mini-m (web-search/SearchGPT backend), NOT the Pro-tier
    multi-section deep research.  Use _build_heavy_dr_payload() for the full DR.
    """
    payload = _build_payload(DR_MODEL, [{"role": "user", "content": query}])
    payload["system_hints"] = ["research"]
    return payload


def _build_heavy_dr_payload(query: str) -> dict:
    """Build payload for heavy Deep Research — the true Pro-tier 5–30 min DR path.

    Ground-truth reverse-engineered from chatgpt.com/deep-research browser traffic
    (2026-04-23).  Key differences from legacy DR:

    * URL target: /backend-api/f/conversation  (frontend endpoint)
    * model: gpt-5-5-pro
    * system_hints: ["connector:connector_openai_deep_research"]
    * thinking_effort: "extended"
    * message.metadata contains deep_research_version / venus_model_variant / caterpillar fields

    The server_ste_metadata from the SSE stream will show tool_name="ApiToolWrapper"
    and tool_invoked=true, confirming the DR connector fired.  The resolved_model_slug
    in the user-message echo is "i-mini-m" (the orchestration layer); the actual heavy
    reasoning runs as a background tool call inside the connector.

    Rate-limited by the "deep_research" feature quota (248 uses / reset cycle for Pro).
    """
    msg_id = str(uuid4())
    return {
        "action": "next",
        "messages": [
            {
                "id": msg_id,
                "author": {"role": "user"},
                "create_time": time.time(),
                "content": {"content_type": "text", "parts": [query]},
                "metadata": {
                    "caterpillar_selected_sources": [],
                    "developer_mode_connector_ids": [],
                    "selected_mcp_sources": [],
                    "selected_sources": [],
                    "selected_github_repos": [],
                    "selected_all_github_repos": False,
                    "system_hints": [HEAVY_DR_HINT],
                    "deep_research_version": "standard",
                    "venus_model_variant": "standard",
                    "serialization_metadata": {"custom_symbol_offsets": []},
                    "user_timezone": "UTC",
                },
            }
        ],
        "parent_message_id": str(uuid4()),
        "model": HEAVY_DR_MODEL,
        "client_prepare_state": "success",
        "timezone_offset_min": -480,
        "timezone": "UTC",
        "conversation_mode": {"kind": "primary_assistant"},
        "enable_message_followups": True,
        "system_hints": [HEAVY_DR_HINT],
        "thinking_effort": "extended",
        "supports_buffering": True,
        "supported_encodings": ["v1"],
        "force_parallel_switch": "auto",
        "paragen_cot_summary_display_override": "allow",
        "history_and_training_disabled": True,
        "force_use_sse": True,
    }


class ConversationClient:
    def __init__(self, backend: BackendClient) -> None:
        self._backend = backend

    async def stream(
        self,
        model: str,
        messages: list[dict],
        tools: list | None = None,
    ) -> AsyncIterator[str]:
        headers = dict(self._backend._session.headers)
        headers["Accept"] = "text/event-stream"
        headers["Content-Type"] = "application/json"

        sentinel = await SentinelGate(self._backend).get_tokens()
        headers["Openai-Sentinel-Chat-Requirements-Token"] = sentinel[
            "chat-requirements"
        ]
        if sentinel.get("proof"):
            headers["Openai-Sentinel-Proof-Token"] = sentinel["proof"]
        if sentinel.get("turnstile"):
            headers["Openai-Sentinel-Turnstile-Token"] = sentinel["turnstile"]

        payload = _build_payload(model, messages)
        if tools:
            payload["tools"] = tools

        async with AsyncSession(impersonate="chrome131", verify=True) as s:
            resp = await s.post(
                _CONV_URL,
                headers=headers,
                json=payload,
                timeout=300,
                stream=True,
            )
            if resp.status_code == 401:
                body = _safe_body(resp)
                raise RuntimeError(
                    "401 Unauthorized — run `codex login`"
                    + (f": {body}" if body else "")
                )
            if resp.status_code == 403:
                body = _safe_body(resp)
                raise RuntimeError(
                    "403 Forbidden — token may have expired"
                    + (f": {body}" if body else "")
                )
            if resp.status_code not in (200, 201):
                body = _safe_body(resp)
                raise RuntimeError(
                    f"HTTP {resp.status_code} from /backend-api/conversation"
                    + (f": {body}" if body else "")
                )

            current_msg_id: str | None = None
            last_text = ""

            def _reset_if_new_msg(msg_id: str | None) -> bool:
                """Return True if this frame starts a new message (caller must not dedupe)."""
                nonlocal current_msg_id, last_text
                if msg_id and msg_id != current_msg_id:
                    current_msg_id = msg_id
                    last_text = ""
                    return True
                return False

            async for raw_line in resp.aiter_lines():
                if isinstance(raw_line, bytes):
                    raw_line = raw_line.decode("utf-8", errors="replace")
                line = raw_line.strip()
                if not line or line.startswith(":") or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue

                # Format A: v-patch (live streaming mode)
                v = obj.get("v")
                if v is not None:
                    if isinstance(v, str):
                        # String v-patch — continuation of current message id
                        if v:
                            yield v
                            last_text += v
                        continue
                    if isinstance(v, dict):
                        msg_id = v.get("message", {}).get("id")
                        is_new = _reset_if_new_msg(msg_id)
                        parts = v.get("message", {}).get("content", {}).get("parts", [])
                        if parts and isinstance(parts[0], str):
                            new = parts[0]
                            if is_new:
                                # New message — yield fresh, don't dedupe against prior stream
                                if new:
                                    yield new
                                    last_text = new
                            elif new.startswith(last_text):
                                delta = new[len(last_text) :]
                                if delta:
                                    yield delta
                                last_text = new
                            elif new:
                                yield new
                                last_text = new
                        continue

                # Format B: full message replacement (history_disabled mode)
                msg = obj.get("message")
                if not isinstance(msg, dict):
                    continue
                if msg.get("author", {}).get("role") != "assistant":
                    continue
                content = msg.get("content", {})
                if content.get("content_type") != "text":
                    continue
                parts = content.get("parts") or []
                if not parts or not isinstance(parts[0], str):
                    continue
                msg_id = msg.get("id")
                is_new = _reset_if_new_msg(msg_id)
                new = parts[0]
                if is_new:
                    if new:
                        yield new
                        last_text = new
                elif new.startswith(last_text):
                    delta = new[len(last_text) :]
                    if delta:
                        yield delta
                    last_text = new
                elif new:
                    yield new
                    last_text = new

    async def complete(self, model: str, messages: list[dict]) -> str:
        chunks: list[str] = []
        async for chunk in self.stream(model, messages):
            chunks.append(chunk)
        return "".join(chunks)

    async def deep_research(self, query: str) -> AsyncIterator[dict]:
        """Stream Deep Research events for *query*.

        Yields dicts of shape:
          {"type": "progress", "text": <partial_text>}   — intermediate text deltas
          {"type": "tool",     "call": <search_call>}    — tool invocations (search/browse)
          {"type": "done",     "text": <full_text>,
           "content_references": [...], "search_result_groups": [...]}

        Uses model='research' + system_hints=['research'] which triggers the
        ChatGPT web-search deep-research backend (confirmed working 2026-04-24).
        Timeout is 1800 s to accommodate multi-minute research runs.
        """
        headers = dict(self._backend._session.headers)
        headers["Accept"] = "text/event-stream"
        headers["Content-Type"] = "application/json"

        sentinel = await SentinelGate(self._backend).get_tokens()
        headers["Openai-Sentinel-Chat-Requirements-Token"] = sentinel[
            "chat-requirements"
        ]
        if sentinel.get("proof"):
            headers["Openai-Sentinel-Proof-Token"] = sentinel["proof"]
        if sentinel.get("turnstile"):
            headers["Openai-Sentinel-Turnstile-Token"] = sentinel["turnstile"]

        payload = _build_dr_payload(query)

        async with AsyncSession(impersonate="chrome131", verify=True) as s:
            resp = await s.post(
                _CONV_URL,
                headers=headers,
                json=payload,
                timeout=1800,
                stream=True,
            )
            if resp.status_code == 401:
                raise RuntimeError("401 Unauthorized — run `codex login`")
            if resp.status_code == 403:
                raise RuntimeError("403 Forbidden — token may have expired")
            if resp.status_code not in (200, 201):
                body = ""
                async for chunk in resp.aiter_content():
                    body += (
                        chunk.decode("utf-8", errors="replace")
                        if isinstance(chunk, bytes)
                        else chunk
                    )
                    if len(body) > 500:
                        break
                raise RuntimeError(
                    f"HTTP {resp.status_code} from /backend-api/conversation: {body[:500]}"
                )

            last_text = ""
            async for raw_line in resp.aiter_lines():
                if isinstance(raw_line, bytes):
                    raw_line = raw_line.decode("utf-8", errors="replace")
                line = raw_line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue

                msg = obj.get("message", {})
                if not isinstance(msg, dict):
                    continue

                role = msg.get("author", {}).get("role", "")
                content = msg.get("content", {})
                ct = content.get("content_type", "")
                status = msg.get("status", "")
                meta = msg.get("metadata", {})

                # Tool invocation events (search/browse)
                if ct == "code" and role == "assistant":
                    call_text = content.get("text", "")
                    if call_text:
                        yield {"type": "tool", "call": call_text}
                    continue

                # Text streaming — assistant in-progress or finished
                if role == "assistant" and ct == "text":
                    parts = content.get("parts") or []
                    new = parts[0] if parts and isinstance(parts[0], str) else ""

                    if status == "finished_successfully":
                        # Emit final done event with citations
                        yield {
                            "type": "done",
                            "text": new,
                            "content_references": meta.get("content_references", []),
                            "search_result_groups": meta.get(
                                "search_result_groups", []
                            ),
                        }
                        last_text = new
                    elif status == "in_progress" and new:
                        # Emit incremental text delta
                        if new.startswith(last_text):
                            delta = new[len(last_text) :]
                            if delta:
                                yield {"type": "progress", "text": delta}
                        else:
                            yield {"type": "progress", "text": new}
                        last_text = new

    async def deep_research_heavy(self, query: str) -> AsyncIterator[dict]:
        """Stream true Pro-tier Deep Research events for *query*.

        Uses the ground-truth payload reverse-engineered from chatgpt.com/deep-research
        (2026-04-23).  Targets /backend-api/f/conversation with:

            model = gpt-5-5-pro
            system_hints = ["connector:connector_openai_deep_research"]
            thinking_effort = "extended"
            message.metadata.deep_research_version = "standard"
            message.metadata.venus_model_variant = "standard"

        Yields dicts of shape:
          {"type": "progress", "text": <partial>}   — streaming text deltas
          {"type": "tool",     "call": <call_text>} — tool/connector invocations
          {"type": "meta",     "data": <ste_meta>}  — server_ste_metadata events
          {"type": "done",     "text": <full_text>,
           "content_references": [...], "search_result_groups": [...]}

        Rate: consumes from the "deep_research" quota (248 uses / reset cycle on Pro).
        Timeout: 1800 s (DR runs can take 5–30 minutes for complex queries).

        Note: the resolved_model_slug in user-message echo will show "i-mini-m"
        (the orchestration layer).  The actual heavy reasoning runs inside the
        connector_openai_deep_research tool call.
        """
        headers = dict(self._backend._session.headers)
        headers["Accept"] = "text/event-stream"
        headers["Content-Type"] = "application/json"

        sentinel = await SentinelGate(self._backend).get_tokens()
        headers["Openai-Sentinel-Chat-Requirements-Token"] = sentinel[
            "chat-requirements"
        ]
        if sentinel.get("proof"):
            headers["Openai-Sentinel-Proof-Token"] = sentinel["proof"]
        if sentinel.get("turnstile"):
            headers["Openai-Sentinel-Turnstile-Token"] = sentinel["turnstile"]

        payload = _build_heavy_dr_payload(query)

        async with AsyncSession(impersonate="chrome131", verify=True) as s:
            resp = await s.post(
                _F_CONV_URL,
                headers=headers,
                json=payload,
                timeout=1800,
                stream=True,
            )
            if resp.status_code == 401:
                raise RuntimeError("401 Unauthorized — run `codex login`")
            if resp.status_code == 403:
                raise RuntimeError("403 Forbidden — token may have expired")
            if resp.status_code not in (200, 201):
                body = ""
                async for chunk in resp.aiter_content():
                    body += (
                        chunk.decode("utf-8", errors="replace")
                        if isinstance(chunk, bytes)
                        else chunk
                    )
                    if len(body) > 500:
                        break
                raise RuntimeError(
                    f"HTTP {resp.status_code} from {_F_CONV_URL}: {body[:500]}"
                )

            last_text = ""
            async for raw_line in resp.aiter_lines():
                if isinstance(raw_line, bytes):
                    raw_line = raw_line.decode("utf-8", errors="replace")
                line = raw_line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue

                # Server-side telemetry / metadata event
                if obj.get("type") == "server_ste_metadata":
                    yield {"type": "meta", "data": obj.get("metadata", {})}
                    continue

                msg = obj.get("message", {})
                if not isinstance(msg, dict):
                    continue

                role = msg.get("author", {}).get("role", "")
                content = msg.get("content", {})
                ct = content.get("content_type", "")
                status = msg.get("status", "")
                meta = msg.get("metadata", {})

                # Tool / connector invocation events
                if ct == "code" and role == "assistant":
                    call_text = content.get("text", "")
                    if call_text:
                        yield {"type": "tool", "call": call_text}
                    continue

                # Text streaming — assistant in-progress or finished
                if role == "assistant" and ct == "text":
                    parts = content.get("parts") or []
                    new = parts[0] if parts and isinstance(parts[0], str) else ""

                    if status == "finished_successfully":
                        yield {
                            "type": "done",
                            "text": new,
                            "content_references": meta.get("content_references", []),
                            "search_result_groups": meta.get(
                                "search_result_groups", []
                            ),
                        }
                        last_text = new
                    elif status == "in_progress" and new:
                        if new.startswith(last_text):
                            delta = new[len(last_text) :]
                            if delta:
                                yield {"type": "progress", "text": delta}
                        else:
                            yield {"type": "progress", "text": new}
                        last_text = new
