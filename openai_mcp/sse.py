"""Native SSE client for /backend-api/conversation — no proxy required."""

from __future__ import annotations

import json
import logging
import re
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
        "timezone_offset_min": -480,
        "history_and_training_disabled": True,
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
