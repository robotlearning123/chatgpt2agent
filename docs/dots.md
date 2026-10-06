# OpenAI dots support

Status: **read + scheduled-work control + async messaging live** (2026-10-04).
Dots are OpenAI's always-on GPT-6 Astra agents (launched 2026-09-29). They
have no documented API; this package drives the surfaces they actually use.

## Tools (8)

- `dots_status` — read-only detection across conversations / catalog /
  account-check / automations (per-surface error-tolerant). `dots_detected`
  flips only on hard markers (non-empty dot-named keys — including the
  conversations envelope and the models payload, dot `conversation_origin`);
  `automations` reports the cloud-executor counts.
  Catalog `astra` slugs never claim detection — `gpt-6-astra-wm` routes to
  `gpt-5-6`. Scan window: the first 50 conversations; when
  `conversations_scan_complete` is false a negative is incomplete, not
  "no dots".
- `list_dots` — the account's dots (aeon registry joined with the first 25
  messaging rooms (wire-verified cap); a room outside that window joins as null).
  Rooms/tbo are PER-ACCOUNT (the aeon id prefix is the account uuid): if
  `~/.codex/auth.json` is rewritten for a different account, the rooms,
  dots, and automations you see all change (2026-10-05: a 13:13Z token
  switch read as "the dot room vanished"). `send_to_dot`'s default
  resolution follows the live registry, so it survives the switch.
- `dot_messages` — the dot conversation (DOT/OWNER-classified, redacted).
- `send_to_dot` — async messaging: delivery verified by room readback; the
  dot replies on its own cadence (see below).
- `list_automations` — the dot's scheduled work (PII-redacted, truncated).
- `create_automation` — **defaults to `enabled=False`**: automations are
  created paused and only run after an explicit
  `set_automation_status(..., enabled=True)` (or the ChatGPT UI).
  `frequency` is validated (daily/weekly/hourly/minutely) — typos raise
  instead of silently scheduling DAILY.
- `set_automation_status` / `remove_automation` — enable/disable/delete.

## Verified wire shape (2026-10-04, by execution)

`POST /backend-api/automations/save` — server-validated schema learned in
three rounds from its own 422 details (title required; `schedule` = full
`BEGIN:VEVENT\nDTSTART:…\nRRULE:…\nEND:VEVENT` string; `timing_mode` = int
enum 0/1/2 = exact/flexible/condition). `set_status` takes
`{jawbone_id, is_enabled}`; `remove` takes `{automation_id}`. Full control
loop verified live through the MCP tools: create-disabled → list →
set_status → remove → confirmed gone.

Evidence the dot is active on the checked account: automations with
`executor: "cloud"` and `aeon_id` (one running MINUTELY/10m as of
2026-10-04T14:45Z). Route names and payload fields were extracted from the
ChatGPT desktop app bundle (`app.asar`) — zero blind fuzzing; the only
write probes were schema-driven (422 detail → correct → success).

## Sending to the dot: async, minutes-level latency (4/4 E2E confirmed)

`send_to_dot` delivers a message into the dot's room. Wire facts
(2026-10-04, all verified by execution):

- `POST /backend-api/messaging/rooms/{room}/messages` with
  `{"content": {"text": ...}}` **persists** the message. Upstream answers
  422 "stable send identifier" even on success (also with a freshly captured
  `x-openai-thread-route` calpico JWT, TTL 300 s) — the tool tolerates the
  422 and judges delivery by readback.
- The dot **does** process API-sent messages, on its own cadence: an
  API-sent "reply PONG-REST" got its `DOT: PONG-REST` answer ~16 minutes
  later (n=1). App-typed messages (driven via CDP for the A/B) got replies
  in ~6-10 s — the desktop app rides a realtime stack (`aeon/prepare`,
  `ios/attestation_challenge`, `celsius/ws/user` websocket) that REST does
  not. Suspected sweep mechanism: the dot's recurring automation runs pick
  up pending room messages.
- E2E record (2026-10-04): PONG-REST ~16 min, PONG-FINAL ~10 min,
  PONG-REVIEW ~8 min, and a six-subbot formation task answered
  `SUBBOTS-DONE 6` in ~8 min with zero side effects. So: programmatic send
  works when minutes-level latency is fine; for instant turnaround, type in
  the ChatGPT desktop app.

Test etiquette note: the 2026-10-04 verification left six clearly-labeled
`[gpt2agent …验证…]` test messages in the dot room; the dot was instructed
to only reply PONG and not act on them.

## Account safety

Read-only GETs and schema-driven writes only; automations are created
disabled by default; PII redaction on all listed prompts/titles. Dots run
under the account's authority — keep human review for consequential dot
work; this package never auto-approves dot actions.
