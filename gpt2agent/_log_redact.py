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

# Matches JSON-encoded session-scoped tokens/headers so we can redact them
# from error messages and logs.
_SENSITIVE_KEY_RE = re.compile(
    r'"(Openai-Sentinel-[A-Za-z-]+-Token|Authorization|OAI-[A-Za-z-]+)"\s*:\s*"[^"]*"',
    re.IGNORECASE,
)


def redact_error(text: str, max_len: int = 200) -> str:
    """Truncate + redact session-scoped tokens before surfacing to the user.

    Strips the values of any ``Openai-Sentinel-*-Token``, ``Authorization``,
    or ``OAI-*`` header-shaped substrings, then truncates to ``max_len``
    so a 1 MB error body doesn't blow up the user's terminal.
    """
    if not isinstance(text, str):
        text = str(text)
    cleaned = _SENSITIVE_KEY_RE.sub(r'"\1":"<REDACTED>"', text)
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "...[truncated]"
    return cleaned
