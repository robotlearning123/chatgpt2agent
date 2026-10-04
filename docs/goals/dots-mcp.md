# Goal: add dots to mcp control

Owner goal (2026-10-04): expose OpenAI dots (always-on GPT-6 Astra agents,
launched 2026-09-29) to MCP clients via gpt2agent.
Owner safety directive mid-goal: "be careful and safely for accounts" —
probing is read-only by default, no payload/enum fuzzing.

## Status: PARTIAL (external gates)

Shipped: `dots_status` MCP tool (tool #31), PR #89, suite green.
Blocked on external gates: send/control tool requires (G1) dots rollout to
reach the account, (G2) dot creation in the ChatGPT desktop UI (owner,
first dot free on Pro), (G3) endpoint evidence from a captured HAR.

## Evidence timeline (all 2026-10-04, account A)

- Read-only spike (spike 08, research repo branch research/dots-mcp):
  me/accounts-check/tasks/models/conversations/conversation-init →
  0 dot-named keys; /backend-api/dots + /dot + /agent_companions → 404.
- One validation round on conversation_mode.kind guesses → HTTP 422 ×3,
  stopped immediately per the safety directive; no conversations created.
- macOS ChatGPT desktop 26.930.31730 (updated 2026-10-03, dots-capable
  build): app data has legacy scheduled-task automations only; the full
  1.6 GB web-profile cache contains zero dots/astra frontend strings →
  rollout has not reached the account.
- Catalog note: gpt-6-astra-wm IS in the account catalog (title
  "GPT-6 Astra", tags [history_off_approved]) but is a plain entry — the
  -wm family routes to gpt-5-6 (verified in v0.0.24 for gpt-6.1-sol).
- Env fix found during goal: host venv was missing sentinel-bridge deps
  (colorama, esprima, pillow) — restored via uv; a venv rebuild loses them
  again (bridge not part of the distribution).

## Deliverables

- gpt2agent PR #89 (branch feat/dots-mcp, commit 511d39f):
  gpt2agent/tools/dots.py (new), tools/__init__.py registration,
  tests/test_dots.py (6 cases incl. positive-marker power tests),
  tests/test_mcp_sdk_compat.py count guard 30→31, docs/dots.md (unlock
  runbook), CHANGELOG Unreleased entry, CLAUDE.md/docs/README counts,
  tools-reference.md entry, verify receipt artifacts/verify/dots-mcp-2026-10-04.md.
- Research repo branch research/dots-mcp: reports/DOTS-MCP-READINESS.md
  (full analysis + HAR runbook + tool design) + spikes/08_dots_spike.py.

## Verification numbers

- bash .claude/verify.sh → 687 passed / 14 skipped / ruff clean
  (was 686 passed + 1 failed before the count-guard update).
- Live dots_status (real account, read-only): dots_detected=False,
  status=not_rolled_out, checked_conversations=50, automation_conversation_ids=[],
  dot_named_fields=[], astra_catalog_slugs=['gpt-6-astra-wm'],
  unknown_conversation_origins=[].
- Real server build: 31 tools registered, dots_status present.
