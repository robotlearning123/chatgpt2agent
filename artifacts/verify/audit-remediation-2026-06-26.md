# Audit remediation — 2026-06-26

Cross-model bug hunt + fix on `gpt2agent` v0.0.7 (branch `fix/audit-2026-06-26`).

## Team
- **cx** (GPT-5.5 #1, codex) — core: sse/backend/auth/sentinel — 8 findings.
- **cx2** (GPT-5.5 #2, isolated CODEX_HOME) — server/tools/install/setup/_vendored — 8 findings (1 P0).
- **ccz** (GLM-5.2 via z.ai) — broad pass — surfaced the unique `complete()` 5-min hang the codex pair missed.
- **Opus** (me) — full ~4700 LOC read; independent findings, high overlap.

## Verification (commands run, real output)
- `pytest tests/` → **120 passed, 9 skipped** (baseline was 102; +17 regression + 1 chat-poll).
- Regression proof: stashed production fixes, ran new tests on unfixed tree → **14/16 failed**
  (the 2 that passed were a parametrization that always worked + a mode test later strengthened).
- Import sanity: all 12 changed modules import clean.
- **cx final verdict (independent):** first pass FAIL — caught a permission regression I introduced
  (`os.open(O_CREAT,0o600)` ignores mode on an existing file). Fixed with `os.fchmod`. Re-verify:
  **PASS** — "existing 0644 token.json ends 0o600 in both paths; fchmod runs on valid fd; no new P0/P1;
  verified pytest tests/test_audit_2026_06_26.py → 17 passed."
- **Opus verdict:** all changes reviewed; minimal, scoped; tests green.

## Fixes (15) — file:finding
Security
- install.py `_backup` — preserve source mode (was umask → secret-bearing config backups world-readable). [cx2 P0]
- install.py `_atomic_write` — open tmp 0o600 up front (no umask window). [cx2 P1]
- auth.py / setup.py token writes — os.open 0o600 + os.fchmod (tightens existing file). [cx P1, cx2 P1]
- _log_redact.py — redact bare `"token"` JSON field (ccz verified leak by execution). [ccz P2]
- tools/_redact.py — redact pasted secrets in tool output (JWT/bearer/API-key), not just PII. [cx2 P1]
- sentinel.py — redact `json.dumps(resp)` not `str(dict)` (single-quote bypass). [cx P2]

Correctness / robustness
- sse.py heavy DR — capture top-level `conversation_id` so Phase-2 poll fires (else async report lost). [cx P1, Opus]
- sse.py `complete()` — gate 300s async poll behind `poll_async` (only agent); normal chat no longer hangs 5 min. [ccz P1]
- sse.py v-patch — `v.get("message") or {}` guard (null message crashed stream). [cx P1]
- backend.py `get()` — non-JSON/empty 2xx guard mirroring `post()`. [cx/ccz P1]
- sentinel.py — guard `r.json()` + dict validation. [cx P1]
- install.py — section regex matches `[[array-of-table]]` (else replacing gpt2agent section deletes a following table). [cx2 P1]
- conversations.py `get_conversation` — follow `current_node` active chain (fallback create_time) instead of raw mapping order. [cx2 P1]
- auth.py `_from_saved` — accept token / nested tokens.access_token (align with backend). [cx P2]
- apps.py — preserve explicit `is_connected: False`. [cx2 P2]
- server.py `load_config` — raise on explicit-but-missing `--config`. [cx2 P2]
- CLAUDE.md — stale test count 60 → 102.

## Deferred (noted, not fixed — would need real frame data / over-redaction risk)
- sse.py metadata JSON-pointer array support (cx P1) — observed traffic uses whole-list replace; speculative.
- sse.py in-band SSE error-frame surfacing (ccz P1) — needs real error-frame samples; the worst symptom
  (5-min hang) is removed by the `complete()` poll-gating fix.
- sse.py sticky `is_connector_dispatch` (ccz P2) — observed traffic resets it via a fresh envelope.

## State
- Committed to local branch `fix/audit-2026-06-26`. NOT pushed (no PR; outward-facing action not authorized).
