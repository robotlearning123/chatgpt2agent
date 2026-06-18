"""Shared helper for redacting session-scoped headers from log/error output.

Both ``sse`` and ``sentinel`` surface raw response text in error messages.
Bearer tokens, Sentinel session tokens, and the ``OAI-*`` device/session
identifiers leak account-tracking metadata. ``redact_error`` is the single
canonical place to scrub those before user-visible output.

Distinct from :mod:`gpt2agent.tools._redact`, which strips PII (emails,
phone numbers) from data returned by MCP tools — separate scopes, kept
separate so a future change to one doesn't accidentally weaken the other.
"""

from __future__ import annotations

import re

# 1. JSON-encoded session-scoped headers — redact the value, keep the key.
_SENSITIVE_KEY_RE = re.compile(
    r'"(Openai-Sentinel-[A-Za-z-]+-Token|Authorization|OAI-[A-Za-z-]+)"\s*:\s*"[^"]*"',
    re.IGNORECASE,
)

# 2. JSON token fields by name — `"access_token":"…"`, `"accessToken":"…"`,
#    `"session_token":"…"`, `"id_token":"…"`, `"refresh_token":"…"`. Covers the
#    nested `"tokens":{"access_token":"…"}` shape too (the pair is matched directly).
_TOKEN_FIELD_RE = re.compile(
    r'"((?:access|session|id|refresh|bearer)[_-]?token|accessToken)"\s*:\s*"[^"]*"',
    re.IGNORECASE,
)

# 3. Bare `Bearer <token>` not wrapped in a JSON key (e.g. echoed plain in a body).
#    Char class covers JWT (`-_.`) plus classic base64 (`+/`) and `=` padding so an
#    RFC-style token like `Bearer abc+def/ghi==` is fully redacted, not partially.
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._~+/\-]+=*", re.IGNORECASE)

# 4. Auth/session cookies, e.g. `__Secure-next-auth.session-token=…`.
_COOKIE_RE = re.compile(
    r"((?:__Secure-|__Host-)?[A-Za-z0-9_.\-]*(?:session-token|auth-token|csrf)[A-Za-z0-9_.\-]*)=[^;\s\"]+",
    re.IGNORECASE,
)

# 5. Token-bearing query params, e.g. `?access_token=…` / `&token=…` / `&accessToken=…`.
_QUERY_TOKEN_RE = re.compile(
    r"([?&](?:access[_-]?token|accessToken|session[_-]?token|sessionToken|auth[_-]?token"
    r"|id_token|refresh_token|token|sig|signature)=)[^&\s\"]+",
    re.IGNORECASE,
)


def redact_error(text: str, max_len: int = 200) -> str:
    """Truncate + redact session-scoped secrets before surfacing to the user.

    Strips header values (``Authorization``/``OAI-*``/``Openai-Sentinel-*-Token``),
    named JSON token fields (``access_token`` and friends), bare ``Bearer <token>``
    strings, auth/session cookies, and token-bearing query params; then truncates
    to ``max_len`` so a 1 MB error body doesn't blow up the user's terminal.

    Redaction runs BEFORE truncation so a secret near the start can't survive by
    being split across the cut.
    """
    if not isinstance(text, str):
        text = str(text)
    cleaned = _SENSITIVE_KEY_RE.sub(r'"\1":"<REDACTED>"', text)
    cleaned = _TOKEN_FIELD_RE.sub(r'"\1":"<REDACTED>"', cleaned)
    cleaned = _BEARER_RE.sub("Bearer <REDACTED>", cleaned)
    cleaned = _COOKIE_RE.sub(r"\1=<REDACTED>", cleaned)
    cleaned = _QUERY_TOKEN_RE.sub(r"\1<REDACTED>", cleaned)
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "...[truncated]"
    return cleaned
