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

## Addendum (2026-10-04 afternoon): control is LIVE — status COMPLETE for scheduled work

The conclusion "dots not rolled out" was overturned: the dot runs on this
account and its recurring work rides /backend-api/automations (internal
codenames aeon/jawbone — the literal string "dot" appears nowhere, which is
why marker scans missed it).

- GET /backend-api/automations: 25 items, all executor=cloud, 2 with
  aeon_id; one dot reporting task ran MINUTELY/10m (last_run
  2026-10-04T14:45:16Z).
- Routes/fields from the desktop app.asar: save/remove/set_status;
  jawbone_id (set_status), automation_id (remove).
- Schema via three server-disclosed 422 rounds: title required; schedule =
  full VEVENT string; timing_mode = int 0/1/2 (exact/flexible/condition).
- NEW tools in PR #89 (commit a858392): list_automations,
  create_automation (disabled by default), set_automation_status,
  remove_automation; dots_status gains an automations evidence block.
- Suite: 693 passed / 14 skipped / ruff clean; count guard 35.
- Live control loop through the MCP tools: create-disabled (id
  6ac271541bcc81909e265a5d99f9539e) → listed → set_status ok → remove ok →
  still present: False. Both throwaway automations cleaned; account back to
  its original 25.
- Remaining gap (not blocking scheduled-work control): direct dot chat
  messaging — dot threads are absent from /backend-api/conversations;
  needs one captured HAR from the desktop app (runbook docs/dots.md).

## Addendum 2 (2026-10-04 evening): full dot surface reverse-engineered

Method: relaunched the Mac ChatGPT app with --remote-debugging-port +
--log-net-log (Chromium net-log), drove the dot UI via CDP (typed and sent
messages), and parsed the net-log for the app's real API calls.

New surfaces found and live-verified:
- GET /backend-api/tbo — the dot registry (aeon instances)
- GET /backend-api/messaging/rooms + /rooms/{id}/messages — the dot DM room
  and full conversation (DOT messages = calpico-member-* author prefix)
- E2E: app-sent message → dot replied "PONG-APP"/"PONG-JWT" in 6-10 s →
  read back via REST.

Send-path boundary (A/B verified): REST POST to the room persists the
message but never wakes the dot, with or without a fresh
x-openai-thread-route calpico JWT (TTL 300 s, from the netlog). The wake
rides the app's realtime stack (attestation + celsius websocket).

Final PR #89 scope (7 tools, 37 total): dots_status, list_automations,
create_automation (disabled-by-default), set_automation_status,
remove_automation, list_dots, dot_messages. Suite: 697 passed / 14 skipped /
ruff clean; verify_release: 0.0.25. Six labeled test messages remain in the
dot room (dot instructed to only reply PONG).

## Addendum 3 (2026-10-04 night): subbot formation verified

Owner task: "test my dot, which can launch 6 subbot". Sent via send_to_dot
(19:06:26): launch up to 6 subbots, each reply "<name> ready", no file/branch/
PR/external side effects, then reply SUBBOTS-DONE <n>. DOT answered exactly
"SUBBOTS-DONE 6" at 19:14:32. No new tbo threads / wham tasks / room authors
— subbots are the dot's internal background agents (room authors remain
exactly dot + owner). Control model: dot orchestration fully controllable via
API (async ~8-16 min cadence); individual subbots only indirectly through
dot instructions; instant wake remains app-only.
