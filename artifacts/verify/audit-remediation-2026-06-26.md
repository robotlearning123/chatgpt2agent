# Audit remediation — 2026-06-26

Cross-model bug hunt + fix on `gpt2agent` v0.0.7 (branch `fix/audit-2026-06-26`).

## Team
- **cx** (GPT-5.5 #1, codex) — core: sse/backend/auth/sentinel — 8 findings.
- **cx2** (GPT-5.5 #2, isolated CODEX_HOME) — server/tools/install/setup/_vendored — 8 findings (1 P0).
- **ccz** (GLM-5.2 via z.ai) — broad pass — surfaced the unique `complete()` 5-min hang the codex pair missed.
- **Opus** (me) — full ~4700 LOC read; independent findings, high overlap.

## Verification (commands run, real output)
- `pytest tests/` → **127 passed, 9 skipped** (baseline was 102; +24 regression + 1 chat-poll).
- `ruff check gpt2agent tests` → **All checks passed**.
- `python -m build --outdir /tmp/gpt2agent-dist.gKbEm1` + `twine check` → **sdist and wheel built as 0.0.8; both PASSED**.
- Isolated wheel smoke in `/tmp/gpt2agent-venv.yXGAiP/venv` → **imports 0.0.8, console script reports 0.0.8, bundled skills present, installed auth prefers `CODEX_HOME` over stale saved token**.
- `shellcheck -e SC2086 -e SC2155 install.sh` → **clean**.
- `python -m compileall -q gpt2agent tests` + JSON parse of `server.json` / plugin manifests → **clean**.
- Version consistency check (`pyproject.toml`, `server.json`, package entry, plugin manifest) → **all 0.0.8**.
- `git diff --check` + added-secret scan over the PR diff → **clean**.
- Prior regression proof: stashed production fixes, ran new tests on unfixed tree → **14/16 failed**
  (the 2 that passed were a parametrization that always worked + a mode test later strengthened).
- Codex follow-up regression proof: focused new tests for setup token shape, auth priority,
  metadata array patches, dispatch replacement, and in-band SSE errors → **5/6 of the initial
  parser/setup tests failed before patch; all 7 focused follow-up tests pass after patch**.
- Import sanity: all 12 changed modules import clean.
- **cx final verdict (independent):** first pass FAIL — caught a permission regression I introduced
  (`os.open(O_CREAT,0o600)` ignores mode on an existing file). Fixed with `os.fchmod`. Re-verify:
  **PASS** — "existing 0644 token.json ends 0o600 in both paths; fchmod runs on valid fd; no new P0/P1;
  verified pytest tests/test_audit_2026_06_26.py → 17 passed."
- **Opus verdict:** all changes reviewed; minimal, scoped; tests green.

## Fixes (21) — file:finding
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
- auth.py `get_token` — prefer Codex auth before saved `~/.gpt2agent/token.json` so `CODEX_HOME` and auto-refresh behavior match backend/setup/docs. [Codex follow-up]
- setup.py `_token_from_saved` — accept token / nested tokens.access_token (align setup wizard with backend/auth). [Codex follow-up]
- apps.py — preserve explicit `is_connected: False`. [cx2 P2]
- server.py `load_config` — raise on explicit-but-missing `--config`. [cx2 P2]
- sse.py metadata patches — support JSON-pointer array indexes for citation metadata (`/content_references/0`, `/search_result_groups/0`). [Codex follow-up]
- sse.py in-band SSE errors — raise redacted `RuntimeError` for common `type=error` / `error` frames instead of silently ignoring them. [Codex follow-up]
- sse.py connector dispatch — a real report that replaces the connector-dispatch placeholder now clears the dispatch flag and can finish normally. [Codex follow-up]
- CLAUDE.md — stale test count 60 → 127.

## Deferred
- No known open P0/P1/P2 from the 2026-06-26 audit remains deferred in this branch.
- Live heavy-DR frame-shape drift remains an operational watch item because ChatGPT private backend traffic is not a stable public API.

## State
- PR #16 (`fix/audit-2026-06-26` → `main`) is open for this release-readiness branch.
- Release tag `v0.0.8` is not created yet; tag/publish remains after PR review/merge.
