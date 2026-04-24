"""Native SSE client for /backend-api/conversation — no proxy required."""

from __future__ import annotations

import asyncio
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
                if not isinstance(obj, dict):
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
            done_emitted = False
            try:
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
                    if not isinstance(obj, dict):
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
                                "content_references": meta.get(
                                    "content_references", []
                                ),
                                "search_result_groups": meta.get(
                                    "search_result_groups", []
                                ),
                            }
                            done_emitted = True
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
            finally:
                if last_text and not done_emitted:
                    yield {
                        "type": "done",
                        "text": last_text,
                        "content_references": [],
                        "search_result_groups": [],
                        "terminated_abnormally": True,
                    }

    async def deep_research_heavy(self, query: str) -> AsyncIterator[dict]:
        """Stream true Pro-tier Deep Research events for *query*.

        Two-phase: (1) SSE kickoff at /backend-api/f/conversation speaking
        "delta_encoding v1" JSON-patches; (2) if the stream closes before the
        assistant message reaches finished_successfully (async DR on complex
        queries), poll /backend-api/conversation/{id} until it does.

        Payload + endpoint ground-truth reverse-engineered from
        chatgpt.com/deep-research browser traffic (2026-04-23):

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
        Timeout: 1800 s for initial SSE; poll phase adds up to 1800 s more.

        Note: the resolved_model_slug in user-message echo will show "i-mini-m"
        (the orchestration layer). The actual heavy reasoning runs inside the
        connector_openai_deep_research tool call.
        """
        # --- Quota guard ---
        # Probe /backend-api/conversation/init (POST) to check deep_research quota.
        # Response shape: limits_progress: [{"feature_name": "deep_research", ...}].
        # Fail-open on probe error; only "remaining <= 0" aborts.
        _INIT_PATH = "/backend-api/conversation/init"
        remaining: int | None = None
        try:
            init_data = self._backend.post(
                _INIT_PATH, json={"conversation_mode_kind": "primary_assistant"}
            )
            limits = (init_data or {}).get("limits_progress") or []
            for lim in limits:
                if isinstance(lim, dict) and lim.get("feature_name") == "deep_research":
                    raw = lim.get("remaining")
                    if raw is not None:
                        remaining = int(raw)
                    break
        except Exception as _exc:
            _log.warning("DR quota check failed (%s) — proceeding anyway", _exc)
        if remaining is not None and remaining <= 0:
            raise RuntimeError(
                f"Deep Research quota exhausted. "
                f"Check {_BASE}{_INIT_PATH} (POST) to verify quota reset."
            )

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

        # --- Phase 1: SSE kickoff with JSON-patch delta parser ---
        # /f/conversation speaks "delta_encoding v1". The first assistant envelope
        # arrives as {"v": {"message": {...}}, "c": N}. Subsequent text chunks
        # arrive as {"p": "/message/content/parts/0", "o": "append", "v": "..."}
        # or the shortcut {"v": "..."} (continuation of last path).
        # Batches: {"p": "", "o": "patch", "v": [<sub_patches>]}.
        state = {
            "conversation_id": None,
            "resume_token": None,
            "current_asst_id": None,
            "asst_text": "",
            "asst_status": "",
            "asst_metadata": {},
            "last_path": None,
            "tool_invoked": False,
            "tool_failed": False,
            "done_emitted": False,
        }

        def _emit_done(events: list) -> None:
            if state["done_emitted"]:
                return
            md = state["asst_metadata"] or {}
            payload: dict = {
                "type": "done",
                "text": state["asst_text"],
                "content_references": md.get("content_references", []) or [],
                "search_result_groups": md.get("search_result_groups", []) or [],
            }
            if state["tool_failed"]:
                payload["connector_failed"] = True
            events.append(payload)
            state["done_emitted"] = True

        def _on_envelope(env: dict, events: list) -> None:
            msg = env.get("message") or {}
            role = (msg.get("author") or {}).get("role")
            recipient = msg.get("recipient")
            content = msg.get("content") or {}
            ct = content.get("content_type")
            if (
                role == "assistant"
                and recipient == "all"
                and ct in ("text", "multimodal_text")
            ):
                state["current_asst_id"] = msg.get("id")
                parts = content.get("parts") or []
                initial = parts[0] if parts and isinstance(parts[0], str) else ""
                state["asst_text"] = initial
                state["asst_status"] = msg.get("status") or ""
                state["asst_metadata"] = msg.get("metadata") or {}
                if initial:
                    events.append({"type": "progress", "text": initial})
                if state["asst_status"] == "finished_successfully":
                    _emit_done(events)
            elif (
                role == "assistant"
                and isinstance(recipient, str)
                and recipient.startswith("api_tool")
            ):
                parts = content.get("parts") or []
                call = parts[0] if parts and isinstance(parts[0], str) else ""
                if call:
                    events.append({"type": "tool", "call": call})
                state["tool_invoked"] = True
            elif role == "tool" and recipient == "all":
                # Tool response — detect connector-not-available errors so
                # the caller can distinguish "DR ran" from "DR silently
                # fell through to i-mini-m because the connector isn't
                # provisioned on this account".
                parts = content.get("parts") or []
                text = parts[0] if parts and isinstance(parts[0], str) else ""
                if text and ("Resource not found" in text or text.startswith("Error")):
                    events.append({"type": "tool_error", "message": text})
                    state["tool_failed"] = True

        def _apply_path(path: str, op: str, value, events: list) -> None:
            if path == "/message/content/parts/0":
                if op == "append" and isinstance(value, str):
                    state["asst_text"] += value
                    if value:
                        events.append({"type": "progress", "text": value})
                elif op == "replace" and isinstance(value, str):
                    if value.startswith(state["asst_text"]):
                        delta = value[len(state["asst_text"]) :]
                        if delta:
                            events.append({"type": "progress", "text": delta})
                    elif value:
                        events.append({"type": "progress", "text": value})
                    state["asst_text"] = value
            elif path == "/message/status":
                if op == "replace" and isinstance(value, str):
                    state["asst_status"] = value
                    if value == "finished_successfully":
                        _emit_done(events)
            elif path == "/message/metadata":
                if op in ("append", "patch") and isinstance(value, dict):
                    state["asst_metadata"] = {**state["asst_metadata"], **value}
                elif op == "replace" and isinstance(value, dict):
                    state["asst_metadata"] = value

        def _apply_patch(obj: dict, events: list) -> None:
            t = obj.get("type")
            if t == "resume_conversation_token":
                state["resume_token"] = obj.get("token")
                if obj.get("conversation_id"):
                    state["conversation_id"] = obj["conversation_id"]
                return
            if t in ("message_marker", "message_stream_complete"):
                if obj.get("conversation_id"):
                    state["conversation_id"] = obj["conversation_id"]
                return
            if t == "server_ste_metadata":
                md = obj.get("metadata") or {}
                if md.get("tool_invoked"):
                    state["tool_invoked"] = True
                events.append({"type": "meta", "data": md})
                return
            if t == "input_message":
                return
            if t is not None:
                return

            p = obj.get("p")
            o = obj.get("o")
            has_v = "v" in obj
            v = obj.get("v")

            # Full envelope: explicit {"p": "", "o": "add", ...}
            # or implicit {"v": {"message": ...}, "c": N}
            if (
                isinstance(v, dict)
                and "message" in v
                and ((p == "" and o == "add") or (p is None and o is None))
            ):
                _on_envelope(v, events)
                state["last_path"] = None
                return

            # Batch patch
            if p == "" and o == "patch" and isinstance(v, list):
                for sub in v:
                    if isinstance(sub, dict):
                        _apply_patch(sub, events)
                return

            # Path-scoped patch
            if isinstance(p, str) and p:
                _apply_path(p, o or "replace", v, events)
                state["last_path"] = p
                return

            # Shortcut: bare "v" continues the last path (text-append)
            if p is None and o is None and has_v and state["last_path"]:
                _apply_path(state["last_path"], "append", v, events)
                return

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

            async for raw_line in resp.aiter_lines():
                if isinstance(raw_line, bytes):
                    raw_line = raw_line.decode("utf-8", errors="replace")
                line = raw_line.strip()
                if not line or line.startswith(":") or line.startswith("event:"):
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue

                events: list[dict] = []
                _apply_patch(obj, events)
                for e in events:
                    yield e

        # --- Phase 2: Async polling fallback ---
        # If the stream closed without finished_successfully AND the DR
        # connector fired, poll /backend-api/conversation/{id} until the
        # real answer lands.
        if (
            not state["done_emitted"]
            and state["conversation_id"]
            and state["tool_invoked"]
        ):
            async for evt in self._poll_dr_completion(
                state["conversation_id"], seed_text=state["asst_text"]
            ):
                yield evt
            return

        if not state["done_emitted"] and state["asst_text"]:
            # Stream ended mid-text without finalize — surface what we have.
            yield {
                "type": "done",
                "text": state["asst_text"],
                "content_references": [],
                "search_result_groups": [],
                "terminated_abnormally": True,
            }

    async def _poll_dr_completion(
        self,
        conv_id: str,
        *,
        seed_text: str = "",
        interval: float = 15.0,
        max_wait: float = 1800.0,
    ) -> AsyncIterator[dict]:
        """Poll /backend-api/conversation/{id} until the DR answer lands.

        Walks mapping[*].message for the latest assistant text node; yields
        incremental progress until its status reaches finished_successfully
        (or max_wait elapses).
        """
        detail_path = f"/backend-api/conversation/{conv_id}"
        deadline = time.monotonic() + max_wait
        last_emitted = seed_text

        while time.monotonic() < deadline:
            await asyncio.sleep(interval)
            try:
                det = await asyncio.to_thread(self._backend.get, detail_path)
            except Exception as exc:
                _log.warning("DR poll error (%s) — continuing", exc)
                continue

            mapping = (det or {}).get("mapping") or {}
            candidates = []
            for node in mapping.values():
                msg = (node or {}).get("message")
                if not isinstance(msg, dict):
                    continue
                if (msg.get("author") or {}).get("role") != "assistant":
                    continue
                recipient = msg.get("recipient")
                if recipient and recipient != "all":
                    continue
                content = msg.get("content") or {}
                if content.get("content_type") not in ("text", "multimodal_text"):
                    continue
                parts = content.get("parts") or []
                text = parts[0] if parts and isinstance(parts[0], str) else ""
                if not text:
                    continue
                candidates.append(
                    (
                        msg.get("create_time") or 0,
                        msg.get("status") or "",
                        text,
                        msg.get("metadata") or {},
                    )
                )
            if not candidates:
                continue
            candidates.sort(key=lambda c: c[0])
            _, latest_status, latest_text, latest_meta = candidates[-1]

            if latest_text != last_emitted:
                if latest_text.startswith(last_emitted):
                    delta = latest_text[len(last_emitted) :]
                    if delta:
                        yield {"type": "progress", "text": delta}
                else:
                    yield {"type": "progress", "text": latest_text}
                last_emitted = latest_text

            if latest_status == "finished_successfully":
                yield {
                    "type": "done",
                    "text": latest_text,
                    "content_references": latest_meta.get("content_references", [])
                    or [],
                    "search_result_groups": latest_meta.get("search_result_groups", [])
                    or [],
                }
                return

        if last_emitted:
            yield {
                "type": "done",
                "text": last_emitted,
                "content_references": [],
                "search_result_groups": [],
                "terminated_abnormally": True,
                "timeout": True,
            }
        else:
            raise RuntimeError(
                f"DR polling timed out after {max_wait}s waiting for conv {conv_id}"
            )
