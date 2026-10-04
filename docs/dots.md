# OpenAI dots support

Status: **detection only** (2026-10-04). Dots are OpenAI's always-on GPT-6
Astra agents (launched 2026-09-29). They have no documented API, roll out
gradually to Pro plans, and a dot can only be created in the ChatGPT desktop
app or desktop web UI. Until a dot exists on the account and real dot traffic
has been captured, this package exposes exactly one honest surface: the
`dots_status` MCP tool.

## What dots_status does

Three read-only GETs (conversations, model catalog, account check) and a
structural marker scan:

- `dots_detected` becomes true only on hard markers: a dot-named field in any
  payload, or a `conversation_origin` naming dots.
- `is_automation_conversation` conversations are reported as candidates
  (`automation_conversation_ids`) but never alone claim detection.
- `astra_catalog_slugs` is context only: `gpt-6-astra-wm` ships in the
  catalog of accounts without dots and routes to `gpt-5-6` like the other
  `-wm` slugs (verified 2026-10-04).

A live `not_rolled_out` result is a powered negative: the unit tests
(`tests/test_dots.py`) prove the same code flips to `detected` when markers
are present.

## Why no send/control tool yet

Fabricating a `send_to_dot` endpoint without evidence would violate the
project's anti-hallucination standard. The evidence base (2026-10-04,
spike `08_dots_spike.py` + macOS desktop app inspection, private research
repo `research/dots-mcp`):

- `me` / `accounts-check` / `tasks` / `models` / `conversations` /
  `conversation/init`: zero dot-named keys.
- `GET /backend-api/dots`, `/dot`, `/agent_companions`: 404.
- One 422 round on `conversation_mode.kind` enum guesses — stopped
  immediately per the account-safety directive (no fuzzing).
- ChatGPT desktop 26.930 on macOS: app data and the full 1.6 GB web profile
  cache contain no dots frontend code — the rollout has not reached the
  account.

## Unlock runbook (owner, ~5 minutes on the Mac)

1. Wait for the dots entry point to appear in the ChatGPT desktop app
   (gradual rollout; `dots_status` flips to `detected` the moment markers
   land in account reads).
2. Create the first dot (included in Pro).
3. DevTools → Network → Preserve log; interact with the dot once (message,
   Activity, a scheduled task).
4. Export the HAR and place it in the private research repo. HAR contains
   credentials — it must never enter this public repo.
5. From the HAR: endpoint spec → gated `send_to_dot` / `dot_activity` tools
   (design in the research repo's `DOTS-MCP-READINESS.md` §5). Dot messaging
   will require `temporary=False` — dot memory is the point of a dot.

## Account safety

Probing discipline: read-only GETs and documented payload shapes only; at
most one validation round when a new surface is probed, then stop; prefer
capturing real traffic over guessing endpoints. Dots conversations also run
under the account's authority — any future control tool surfaces explicit
confirmation for consequential actions rather than automating approvals.
