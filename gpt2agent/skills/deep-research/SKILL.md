---
name: deep-research
version: 0.1.0
description: |
  ChatGPT Pro Deep Research via gpt2agent. Two modes: light (model=research,
  30-120s, citations preserved) and heavy (gpt-5-5-pro + connector, 5-30 min,
  long-form report, citations currently lost due to upstream wrapper bug).
  Reuses ~/.codex/auth.json — no extra login. Costs 1 quota per call out of
  Pro monthly budget (248/cycle). Output saved as Markdown.
  Use when asked to "deep research", "DR", "ChatGPT deep research",
  "research <topic>", "go deep on <topic>", or when a question genuinely
  needs web-augmented multi-source synthesis beyond what training data covers.
allowed-tools:
  - Bash
  - Read
  - Write
---

# /deep-research — ChatGPT Pro Deep Research

Calls `gpt2agent`'s `deep_research` / `deep_research_heavy` directly via
pipx Python (bypasses MCP — works even before Claude Code session restart).

## Preconditions (check once)

```bash
command -v gpt2agent >/dev/null || \
  echo "gpt2agent not installed; run: pipx install git+https://github.com/robotlearning123/gpt2agent.git"
test -f ~/.codex/auth.json || echo "Codex token missing; run: codex login"
~/.claude/skills/deep-research/bin/quota.sh   # prints remaining DR quota
```

## Usage

```bash
~/.claude/skills/deep-research/bin/run.sh [--heavy] [-o OUT_DIR] "<query>"
```

- Default mode: **light** (`deep_research`, ~1 min, citations included).
- `--heavy`: **deep_research_heavy** (5-30 min, gpt-5-5-pro + connector,
  long-form report; citation URLs are currently NOT recovered — view in
  chatgpt.com web UI of the same conversation if needed).
- `-o OUT_DIR`: output directory (default: `./research/dr-YYYYMMDD-HHMM/`).
- Query can be inline string, `-` for stdin, or `@file.md` to read from file.

The script writes:
- `report.md` — final report (reconstructed for heavy mode)
- `events.jsonl` — all raw SSE events (for debugging / re-extraction)
- `status.txt` — START / DONE / ERROR with elapsed seconds + event counts
- `meta.json` — server metadata (model slug, request id, etc.)

## When to invoke

| Situation | Mode |
|---|---|
| Quick factual question with citations | light |
| Literature review, market scan, technical decision matrix | light |
| Big strategic question (>5 questions, want 10+ KB report) | heavy |
| Question that *might* yield 50+ sources | heavy |

Skip this skill for: pure code questions, debugging, tasks the user
explicitly wants you to handle locally, anything covered by `context7`
(library docs) or local files.

## How to use in conversation

1. If the user provides a clear topic, draft a 3-8 question structured
   query (research questions + context + deliverable shape) and **show it
   to the user before firing** so they can edit / approve. Heavy mode
   especially deserves a query review — it costs ~10 min and 1/248 quota.
2. Save the approved query to a file (avoids shell escaping issues with
   long multi-line queries):
   ```bash
   cat > /tmp/dr_query.txt <<'EOF'
   <your structured query>
   EOF
   ```
3. Run:
   ```bash
   ~/.claude/skills/deep-research/bin/run.sh [--heavy] -o /path/to/out @/tmp/dr_query.txt
   ```
4. Use `run_in_background: true` for heavy mode — it takes minutes. Tail
   `status.txt` or `events.jsonl` `wc -l` to monitor progress; the bash
   completion notification will arrive when finished.
5. After completion: Read `report.md`, summarize key findings in 5-8
   bullets for the user, point to the full file path.

## Known limitation (upstream bug)

`deep_research_heavy` in `gpt2agent 0.0.1` emits its `done` event on
the FIRST assistant message (which contains only the connector-call JSON,
not the real report). The real report streams afterward as `progress`
events with no second `done`, so the wrapper's `content_references` field
is always empty. This script reconstructs the report from progress events
but cannot recover citation URLs. The light `deep_research` path is
unaffected — use it when citations matter.

Upstream tracking: see `gpt2agent/sse.py` (https://github.com/robotlearning123/gpt2agent/blob/main/gpt2agent/sse.py)
around the `_emit_done` / `_apply_path('/message/status', ...)` logic.

## Quota management

Pro plan: 248 DR calls / monthly cycle (resets ~the 21st). Check before
heavy calls:

```bash
~/.claude/skills/deep-research/bin/quota.sh
```

Refuse to fire `--heavy` if remaining < 10 unless the user explicitly
acknowledges the consumption.

## Account limits & concurrency (IMPORTANT — read before launching)

The DR *quota* (≈248/cycle) is NOT the only limit. The ChatGPT backend also
rate-limits the conversation endpoints per account.

**Run heavy DR SERIALLY — never concurrently.** One heavy DR at a time. While a
heavy DR is running (it polls `/backend-api/conversation/{id}` every ~15s during
its 5–30 min Phase-2 wait), do NOT launch anything else that hits the same
account's chatgpt.com backend — a second heavy/light DR, `codex`/`cx` exec jobs,
agent mode, or `get_conversation`/`list_conversations` polling. Two pollers on
one account collide.

**Observed failure (2026-06-03):** running a heavy DR concurrently with several
`codex` jobs caused sustained **HTTP 429** on the poll for ~30 min, then the run
died with `ERROR  RuntimeError: DR polling timed out after 1800.0s waiting for
conv <id>` and `events.jsonl` had only the initial `meta` event. The exact
per-account request-rate limit is not officially documented — do not assume a
number; just keep account access serial.

**Recovery from a 429 / poll-timeout (no extra quota):** the run almost always
*completed server-side* — only the local poll failed. The `conv_id` is in the
error line. Recover the finished report instead of re-running `--heavy` (which
would burn another quota): GET `/backend-api/conversation/<conv_id>` via
`BackendClient` (or the `get_conversation` MCP tool), then walk
`mapping[*].message` for the newest assistant text node with status
`finished_successfully` — its `metadata.content_references` holds the citation
URLs. NOTE: heavy DR via the connector may render an "embedded UI experience"
and never write a fetchable report node back; in that case there is nothing to
recover and the run must be redone in a quiet window. Wait for the rate limit to
ease first — repeated GETs while rate-limited keep it hot.
