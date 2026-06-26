"""Sentinel gate: fetch chat-requirements, solve POW + turnstile."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from curl_cffi.requests import AsyncSession

from gpt2agent._log_redact import redact_error as _redact_error
from gpt2agent._vendored import pow as _pow
from gpt2agent._vendored import turnstile as _turn

if TYPE_CHECKING:
    from gpt2agent.backend import BackendClient

_log = logging.getLogger(__name__)

_CHAT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class SentinelGate:
    def __init__(self, backend: "BackendClient") -> None:
        self._backend = backend

    async def get_tokens(self) -> dict[str, str]:
        headers = dict(self._backend._session.headers)
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "*/*"

        ua = headers.get("User-Agent") or _CHAT_UA
        p = _pow.get_requirements_token(ua)

        url = "https://chatgpt.com/backend-api/sentinel/chat-requirements"

        async with AsyncSession(impersonate="chrome131", verify=True) as s:
            r = await s.post(url, headers=headers, json={"p": p}, timeout=20)

        if r.status_code != 200:
            body = r.text if hasattr(r, "text") else str(r.content)
            raise RuntimeError(
                f"sentinel/chat-requirements HTTP {r.status_code}: "
                f"{_redact_error(body)}"
            )

        try:
            resp = r.json()
        except Exception as exc:
            body = r.text if hasattr(r, "text") else str(r.content)
            raise RuntimeError(
                f"sentinel/chat-requirements non-JSON 200: {_redact_error(body)}"
            ) from exc
        if not isinstance(resp, dict):
            raise RuntimeError(
                "sentinel/chat-requirements unexpected response shape: "
                f"{_redact_error(json.dumps(resp, ensure_ascii=False))}"
            )
        chat_token = resp.get("token")
        if not chat_token:
            # Redact json.dumps(...) not str(dict): the latter uses single
            # quotes and would bypass the JSON-key redaction regexes.
            raise RuntimeError(
                "sentinel/chat-requirements no token: "
                f"{_redact_error(json.dumps(resp, ensure_ascii=False))}"
            )

        out: dict[str, str] = {"chat-requirements": chat_token}

        pow_block = resp.get("proofofwork") or {}
        if pow_block.get("required"):
            seed = pow_block.get("seed")
            diff = pow_block.get("difficulty")
            if not seed or not diff:
                raise RuntimeError(f"sentinel POW missing seed/difficulty: {pow_block}")
            out["proof"] = _pow.solve_pow(seed, diff, ua)
        else:
            out["proof"] = ""

        turn_block = resp.get("turnstile") or {}
        if turn_block.get("required"):
            dx = turn_block.get("dx")
            if dx:
                proof_for_xor = out.get("proof") or p
                tok = _turn.solve_turnstile(dx, proof_for_xor)
                if tok:
                    out["turnstile"] = tok

        return out
