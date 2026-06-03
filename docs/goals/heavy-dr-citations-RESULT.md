# Heavy DR Citations Result

## Summary

- Branch: `fix/heavy-dr-citations`
- DR quota spent: 2 heavy calls
- Root cause status: H2-compatible parser bug fixed offline; live H1/H2
  confirmation still needs a successful conversation-detail GET because the
  backend returned repeated `HTTP 429` during live diagnosis.

## Evidence

- Source behavior before this patch:
  - `_emit_done` read only `state["asst_metadata"]` for
    `content_references` and `search_result_groups`
    (replaced by `gpt2agent/sse.py:1175-1182`).
  - `_poll_dr_completion` read only the latest assistant text node metadata
    (`gpt2agent/sse.py:1487-1516` now contains the replacement fallback).
- Captured raw Phase 1 evidence:
  - Command:
    `grep -cE 'content_references|safe_urls' /tmp/gpt2agent-heavy-raw-before.jsonl`
  - Output: `2`
  - Both hits were raw SSE assistant/app nodes whose
    `metadata.content_references` were empty lists.
- Free diagnosis:
  - Recent conversation-detail scans found the newest heavy-shaped conversation
    with `deep_research_version: "standard"` and
    `system_hints: ["connector:connector_openai_deep_research"]`, but its final
    hidden assistant node had empty `metadata.content_references` and
    `metadata.search_result_groups`.
  - Subsequent detail GETs for live heavy probe conversations returned
    `HTTP 429`, so the live raw detail fixture could not be captured.

## Fix

- Added `GPT2AGENT_RAW_DUMP=<path>` support:
  - Phase 1 writes each raw SSE JSON object as JSONL.
  - Phase 2 writes each successful conversation-detail poll response as JSONL.
- Added nested metadata patch handling for paths such as
  `/message/metadata/content_references` and
  `/message/metadata/search_result_groups`.
- `_emit_done` now falls back to the last citation-bearing assistant metadata
  observed in the stream.
- `_poll_dr_completion` now searches the full conversation mapping for
  same-turn citation metadata when the latest final text node lacks refs.
- Polling is less aggressive: default interval is 120 seconds, and `HTTP 429`
  backs off for at least 300 seconds.

## Before/After Counts

Offline H2 fixture:

```text
before_latest_meta_refs 0
before_latest_meta_groups 0
after_done_refs 1
after_done_groups 1
after_first_url https://openai.com/
```

Live heavy probe:

```text
before raw Phase 1 content_references: []
after live status: FAIL, repeated HTTP 429 on /backend-api/conversation/{id}
```

## Criteria

- C1 raw-capture: PASS for Phase 1 raw SSE dump.
  Phase 2 dump path is implemented, but no successful Phase 2 detail response
  was received during live runs because the backend returned `HTTP 429`.
- C2 offline parser test: PASS for parser behavior, but live-captured raw detail
  fixture remains blocked by `HTTP 429`.
- C3 end-to-end heavy harness: FAIL.
  Two short heavy probes were attempted. Both reached Phase 2; the first was
  stopped after repeated `HTTP 429`, and the second was stopped after repeated
  `HTTP 429` with the patched backoff.
- C4 no regression: PASS.
  `uv run --extra dev pytest tests/ -q` returned
  `40 passed, 9 skipped in 2.71s`; the known light fixture has
  `refs=93`, `groups=26`, and `item_urls=92`.

## Residual Risk

- Live H1 vs H2 is not fully resolved until a heavy conversation-detail GET
  succeeds after backend rate limiting clears.
- The fallback intentionally prefers same-turn metadata by `working_turn_id` or
  `turn_exchange_id`; if ChatGPT omits both fields, it falls back to the latest
  citation-bearing metadata in the mapping.
