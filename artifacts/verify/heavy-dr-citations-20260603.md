# Verify receipt — Deep Research fixes (0.0.3)

Date: 2026-06-03. Verifier: Opus (Claude). Branch: `fix/heavy-dr-citations`.

## What was claimed vs what was verified

| Change | Claim | Verification | Verdict |
|---|---|---|---|
| Light report extraction (`deep_research.py`) | first `done` was a tool-dispatch artifact; real report discarded | Replayed captured `events.jsonl` (GUIDE run) through patched logic | **VERIFIED** |
| `CODEX_HOME` multi-account (`backend.py`) | reads `$CODEX_HOME/auth.json` over `~/.codex` | 2 unit tests + live route to cx2 account | **VERIFIED** |
| Heavy poll 429 backoff / raw-dump | reduce 429s; capture raw heavy shape | live cx2 run produced 32 raw records, 15 polls | **VERIFIED (instrumentation works)** |
| Heavy citation *extraction* (cx, `sse.py`) | recovers `content_references` for heavy DR | live cx2 run: no report node, no refs ever produced | **NOT VERIFIABLE — data path does not occur** |

## Real-run receipt (the decisive test)

Command:
```
CODEX_HOME=~/.codex-cx2 PYTHONPATH=<worktree> GPT2AGENT_RAW_DUMP=/tmp/cx2-heavy-raw.jsonl \
  ~/.claude/skills/deep-research/bin/run.sh --heavy -o <out> @<short citation-seeking query>
```
Account: cx2 (acct `606e1424…`, Pro, distinct from the main account), quota 229,
**uncontended** (main account's codex loops do not touch it — no 429).

Result (read from real output, not CI/worker say-so):
```
status.txt: ERROR  RuntimeError: DR polling timed out after 1800.0s
            waiting for conv 6a2091b3-1bc0-83ea-a5fa-a5d6877b93e6   elapsed=1821s
raw dump:   32 records, 15 polls, async_status 7×4 → None×11
final poll (11 nodes): report assistant node = 0 chars, content_references=0, search_result_groups=0
tool response node (157 chars): "Rendered a widget that contains the deep research experience"
no `done` event emitted
```

## Conclusion

Heavy DR via `connector_openai_deep_research` renders an embedded-UI experience and
does NOT write a programmatically-fetchable report back into
`/backend-api/conversation/{id}`. The "heavy loses citations" premise is therefore
moot — there is no report node to carry citations. The heavy citation-extraction
code is retained as dormant best-effort and is **documented honestly** (CHANGELOG +
SKILL.md), not shipped as a verified fix. Light mode is the supported path for
programmatic cited research.

## Test suite

`SKIP_LIVE=1 uv run --extra dev pytest tests/ -q` → see run log at release time.
