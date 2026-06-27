import re

# PII patterns.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d[\d ()\-]{8,}\d")

# Secret patterns. Users routinely paste API keys / tokens into ChatGPT, so they
# end up in memories, tasks, and custom instructions — which these tools return
# verbatim. Redact the common structured-secret shapes here so tool OUTPUT never
# echoes one back. Kept separate from gpt2agent._log_redact (which scrubs session
# headers from error bodies) so a change to one scope can't silently weaken the
# other. Each pattern is long/structured enough not to match ordinary prose.
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._~+/\-]{16,}=*", re.IGNORECASE)
_APIKEY_RE = re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}")
_GH_TOKEN_RE = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")


def redact(s: object) -> object:
    if not isinstance(s, str):
        return s
    # Secrets first (a JWT/bearer must not survive by being partly eaten later).
    s = _JWT_RE.sub("<JWT>", s)
    s = _BEARER_RE.sub("Bearer <REDACTED>", s)
    s = _APIKEY_RE.sub("<APIKEY>", s)
    s = _GH_TOKEN_RE.sub("<TOKEN>", s)
    s = _EMAIL_RE.sub("<EMAIL>", s)
    s = _PHONE_RE.sub("<PHONE>", s)
    return s
