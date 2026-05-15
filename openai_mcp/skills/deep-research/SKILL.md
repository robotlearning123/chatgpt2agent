---
name: deep-research
version: 0.1.0
description: |
  ChatGPT Pro Deep Research via openai-mcp. Two modes: light (model=research,
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

Calls `openai-mcp`'s `deep_research` / `deep_research_heavy` directly via
pipx Python (bypasses MCP — works even before Claude Code session restart).

## Preconditions (check once)

```bash
test -x /home/robot/.local/share/pipx/venvs/openai-mcp/bin/python || \
  echo "openai-mcp not installed; run: pipx install git+https://github.com/robotlearning123/chatgpt2agent.git"
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

`deep_research_heavy` in `openai-mcp 0.0.1` emits its `done` event on
the FIRST assistant message (which contains only the connector-call JSON,
not the real report). The real report streams afterward as `progress`
events with no second `done`, so the wrapper's `content_references` field
is always empty. This script reconstructs the report from progress events
but cannot recover citation URLs. The light `deep_research` path is
unaffected — use it when citations matter.

Upstream tracking: see `/home/robot/workspace/47-chatgpt2agent/chatgpt2agent/openai_mcp/sse.py`
around the `_emit_done` / `_apply_path('/message/status', ...)` logic.

## Quota management

Pro plan: 248 DR calls / monthly cycle (resets ~the 21st). Check before
heavy calls:

```bash
~/.claude/skills/deep-research/bin/quota.sh
```

Refuse to fire `--heavy` if remaining < 10 unless the user explicitly
acknowledges the consumption.
