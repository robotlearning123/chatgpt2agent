# OpenAI dots support

Status: **scheduled-work control live** (2026-10-04). Dots are OpenAI's
always-on GPT-6 Astra agents (launched 2026-09-29). They have no documented
API, but their recurring work rides the automations service, which this
package now drives end-to-end. Direct dot messaging is still gated (below).

## Tools

- `dots_status` — read-only detection across conversations / catalog /
  account-check / automations. `dots_detected` flips only on hard markers
  (dot-named keys, dot `conversation_origin`); `automations` reports the
  cloud-executor counts (the dot runtime surface). Catalog `astra` slugs
  never claim detection — `gpt-6-astra-wm` routes to `gpt-5-6`.
- `list_automations` — the dot's scheduled work (PII-redacted, truncated).
- `create_automation` — **defaults to `enabled=False`**: automations are
  created paused and only run after an explicit
  `set_automation_status(..., enabled=True)` (or the ChatGPT UI).
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

## Sending to the dot: async, minutes-level latency

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
- So: programmatic send works when minutes-level latency is fine; for
  instant turnaround, type in the ChatGPT desktop app.

Test etiquette note: the 2026-10-04 verification left six clearly-labeled
`[gpt2agent …验证…]` test messages in the dot room; the dot was instructed
to only reply PONG and not act on them.

## Account safety

Read-only GETs and schema-driven writes only; automations are created
disabled by default; PII redaction on all listed prompts/titles. Dots run
under the account's authority — keep human review for consequential dot
work; this package never auto-approves dot actions.
