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

## Still gated: direct dot messaging

No endpoint evidence yet for messaging the dot's own chat thread
(`thread_mode: existing_chat`, dot threads do not appear in
`/backend-api/conversations`). Unlock runbook: with the dot's chat open in
the desktop app, capture one interaction via DevTools HAR (contains
credentials — private repo only); the endpoint spec from that HAR turns into
a `send_to_dot` tool. Dot messaging will require `temporary=False` — dot
memory is the point of a dot.

## Account safety

Read-only GETs and schema-driven writes only; automations are created
disabled by default; PII redaction on all listed prompts/titles. Dots run
under the account's authority — keep human review for consequential dot
work; this package never auto-approves dot actions.
