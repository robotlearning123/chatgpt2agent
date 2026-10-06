# gpt2agent

MCP server exposing full ChatGPT Plus/Pro account features to any MCP client.

## Build & Test

```bash
bash .claude/verify.sh              # full offline suite + ruff (uv --extra dev)
python -m gpt2agent run             # start MCP server (stdio)
```

## Key Files

- `gpt2agent/server.py` — MCP tool registration (38 tools), config loading
- `gpt2agent/sse.py` — Async SSE client for `/backend-api/conversation` + `/f/conversation` (chat, DR, agent, image gen, code interpreter, canvas); sentinel bridge integration; v1 delta-encoding parser; usage-cap pre-flight; inline citation rendering
- `gpt2agent/sim.py` — Shared simulation profile: one persistent browser identity (impersonation, UA, device/session ids, geo) for seed→mint→prepare→POST
- `gpt2agent/sentinel_bridge.py` — Owner-supplied bridge loader (fingerprint p + PoW + VM turnstile + conduit); opt-in via ENABLED marker or env
- `gpt2agent/citations.py` — DR inline citation rendering (citeturn markers → [N](url))
- `gpt2agent/browser.py` — Playwright Chrome transport (optional extra `gpt2agent[browser]`)
- `gpt2agent/backend.py` — Sync HTTP client (`curl_cffi`), token management
- `gpt2agent/tools/` — Tool modules (21 of 38; the 6 SSE chat/DR tools, usage_stats, and the 4 queue tools live in server.py)
- `gpt2agent/sim.py` — Shared website-simulation identity (persistent device/session IDs, impersonation, geo-consistent timezone/locale)
- `gpt2agent/ratelimit.py` — Shared client-side budget: file-backed sliding window + upstream cooldown registry, cross-process for multi-agent fleets
- `gpt2agent/sentinel.py` — Legacy POW + Turnstile gate (fallback path)

## Critical Invariants

- `temporary=True` (chat default) sets `history_and_training_disabled=True`, blocking image gen, code interpreter, canvas, and memory writes. Tools needing these MUST pass `temporary=False`.
- Deep Research requires `temporary=False` (refuses temporary chats).
- `manual=True` > `browser=True` > REST (transport precedence).
- Token reloaded from `~/.codex/auth.json` or `~/.gpt2agent/token.json` on each request (mtime check).
- `BackendClient` is synchronous. Async tools must wrap in `asyncio.to_thread()`.
- Sentinel bridge is opt-in: `~/.gpt2agent/sentinel-bridge/ENABLED` marker or `GPT2AGENT_SENTINEL_BRIDGE` env. `GPT2AGENT_SENTINEL_BRIDGE_OFF=1` forces legacy path (tests set this in conftest.py).
- The bridge directory is NOT part of this distribution — see docs/dev/specs/sentinel-vm.md for the replacement spec.

## Testing

- Offline: `bash .claude/verify.sh` (full unit/contract suite + ruff; live auto-skip via SKIP_LIVE)
- Evidence trail: sanitized release receipts in `artifacts/verify/`; raw frames may contain resume tokens and must stay outside tracked release files.
- Live matrix: `scripts/agent-user-journey.sh <worktree>` (15 cases)
- Release gate: `scripts/release-emulation-test.sh <worktree>` (11 checks)
- Parameter contracts: `tests/test_param_matrix.py` (34 cases)
- Wire-probe rule: unit fakes cannot validate wire truth (2026-10-04:
  FakeClient accepted `rooms?limit=50`, live backend 422s; cap is 25). Any
  NEW or CHANGED query param / payload field on a live surface needs ONE
  live probe before merge, recorded in the docstring or receipt: read-only
  GET for query params; for write payloads, a schema-driven 422 probe on a
  disposable target (the automations precedent, docs/dots.md).

## Review

Non-trivial diffs follow [REVIEW.md](REVIEW.md) — repo-specific always-check
rules and the verification bar for reviewers.

## Merge gate mechanics (learned 2026-10-04/05)

- Ruleset 16935748 (protect-main) blocks on UNRESOLVED REVIEW THREADS and
  required checks. A `PATCH .../rulesets/{id}` relax attempt 404'd with the
  fleet token (2026-10-05; the documented update method is PUT, so that
  attempt proved nothing about token capability) — irrelevant in practice:
  close the threads instead (adjudicate each against HEAD: fix /
  already-fixed / doc); it needs no protection change at all.
- The classic layer's `required_pull_request_reviews` block = 1 approval by
  default. Authorized relax: PUT protection with `required_pull_request_reviews: null`
  → merge → restore (with a trap) → verify restoration. `--admin` is hook-blocked.
- CI "failure" with EMPTY job steps (killed ~15m): first hypothesis is
  runner starvation, not code (2026-10-05: `gh run rerun --failed` went
  green). Rerun and watch; only if a rerun reproduces it does the workflow
  config deserve investigation.

## Release

1. Bump version in 4 files: pyproject.toml, __init__.py, plugin.json, server.json
   (server.json has BOTH a top-level `version` and `packages[0].version`)
2. Add CHANGELOG.md entry
3. `python scripts/verify_release.py`
4. Merge PR, tag merge SHA (annotated tag), push tag
5. CI publishes to PyPI (trusted publishing) + GitHub Release
6. Verify the tag's Release run went green + `gh release view` + PyPI version
   (tag push alone ≠ published)
7. `scripts/fleet-sync.sh origin/main` — the fleet runs an editable install
   pointing at /home/robot/workspace/47-chatgpt2agent/gpt2agent, NOT the dev
   worktree; unsynced = fleet on old version (2026-09-18 incident)
8. Same-session cleanup: remove merged worktrees/branches, repoint editable
   installs, kill leftover background shells (docs/release-validation.md §8)
9. Full runbook: docs/release-validation.md (incl. owner publish gate)
