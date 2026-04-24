"""Sentinel gate: fetch chat-requirements, solve POW + turnstile."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from curl_cffi.requests import AsyncSession

from openai_mcp._vendored import pow as _pow
from openai_mcp._vendored import turnstile as _turn

if TYPE_CHECKING:
    from openai_mcp.backend import BackendClient

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
            body = r.text[:400] if hasattr(r, "text") else str(r.content[:400])
            raise RuntimeError(
                f"sentinel/chat-requirements HTTP {r.status_code}: {body}"
            )

        resp = r.json()
        chat_token = resp.get("token")
        if not chat_token:
            raise RuntimeError(f"sentinel/chat-requirements no token: {resp}")

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
