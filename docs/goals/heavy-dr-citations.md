# Goal: Recover citation URLs in deep_research_heavy (heavy mode)

Owner brief prepared by Opus (Claude) after reading sse.py + 23 local fixtures, 2026-06-03.
You (cx/codex) are the WRITER. Opus will review your diff before it merges. Work ONLY in
this worktree.

## The bug
- LIGHT mode (`deep_research`) captures citations fine. Proven: 23 local `events.jsonl`
  fixtures under ~/workspace/**/research have populated `content_references`. It reads
  `meta["content_references"]` off the assistant text message whose status is
  `finished_successfully` (sse.py, light path ~line 521-531 in the installed copy).
- HEAVY mode (`deep_research_heavy`) emits its `done` event with `content_references: []`.
  Both finalize paths read refs from `message.metadata`:
    * Phase 1 `_emit_done`  -> `state["asst_metadata"].get("content_references")`
    * Phase 2 `_poll_dr_completion` -> `latest_meta.get("content_references")`
  In heavy runs those come back empty, so the harness Sources section is never built.
- The harness (`~/.claude/skills/deep-research/bin/deep_research.py:73`) saves only the
  wrapper's PROCESSED events, NOT raw SSE. So the URLs are not even recoverable from past
  heavy runs. THIS IS WHY STEP 1 IS RAW CAPTURE.

## Unknown to resolve (root cause)
Does the heavy stream/poll EVER deliver content_references, and under what path/op/node?
Two leading hypotheses — your raw capture must decide which:
  (H1) refs ARE in the stream/poll metadata but arrive AFTER `_emit_done` already fired
       (ordering bug) or under a metadata patch path the parser doesn't merge.
  (H2) the heavy conversation-detail (`GET /backend-api/conversation/{id}`) stores
       content_references on a DIFFERENT mapping node / key than the text node the poller
       reads, so `latest_meta` is the wrong metadata object.

## Citation data shape (ground truth from light fixtures = the TARGET your fix must produce)
`done.content_references[]` entries have keys:
  matched_text, prefix, start_idx, end_idx, safe_urls[], refs, alt, prompt_text, type,
  items[]{title,url,attribution,pub_date,snippet,...}, fallback_items, status, error, style
URLs live at `ref["items"][i]["url"]` AND `ref["safe_urls"][]`.
`search_result_groups[]` entries: {type, domain, entries[]{type,url,title,snippet,ref_id}}.
Sample fixture to study: /home/robot/workspace/50-open-dynamic-workflow/research/competitive-landscape/events.jsonl
(its `done` event has 93 content_references, 26 search_result_groups).

## FREE diagnosis path (DO THIS FIRST — no quota)
A real finished heavy DR conversation already exists server-side with citations.
1. Use the gpt2agent backend to list recent conversations and/or GET a finished heavy
   conversation detail:  `BackendClient().get(f"/backend-api/conversation/{conv_id}")`.
   The most recent finished heavy DR conversation is your free fixture.
   (There is a concurrent heavy run finishing around 2026-06-03 ~11:15-11:45 in
    /home/robot/workspace/51-amazon/research/dr-amazon-ai-cn-sellers-* — once it finishes,
    its conversation is an ideal free fixture. You can also call list_conversations.)
2. Walk `mapping[*].message`; find assistant text node(s) with status finished_successfully;
   inspect WHERE content_references actually live (which node, which metadata key).
   Save the raw detail JSON as a test fixture under tests/fixtures/.
Only if the free path is insufficient, run heavy probes (cap 5, short queries).

## Criteria (measurable)
- [ ] C1 raw-capture: add env-gated raw dump (env var GPT2AGENT_RAW_DUMP=<path>) inside
      deep_research_heavy Phase 1 SSE loop AND Phase 2 poll, writing each raw obj/detail
      as JSONL. verify: `GPT2AGENT_RAW_DUMP=/tmp/raw.jsonl <heavy probe>` then
      `grep -cE 'content_references|safe_urls' /tmp/raw.jsonl` -> diagnose presence.
- [ ] C2 offline parser test: extend tests/test_heavy_dr_parser.py with the captured
      fixture; assert the (fixed) parser yields a done event with >=1 content_reference
      whose items[].url is a real URL. verify: `pytest tests/test_heavy_dr_parser.py -q` exit 0.
- [ ] C3 end-to-end: one real heavy run via the deep-research harness pointed at THIS
      worktree (PYTHONPATH=<worktree>) -> status.txt shows `refs=N` (N>0) and report.md
      has a populated `## Sources`. (Do NOT edit the installed uv tool copy.)
- [ ] C4 no regression: `pytest tests/ -q` exit 0; a light fixture still extracts refs.

## Constraints
- Edit ONLY files inside this worktree. NEVER touch ~/.claude, ~/.agents, .claude/skills,
  or the installed uv tool at ~/.local/share/uv/tools/gpt2agent. Test against the worktree
  via PYTHONPATH=<worktree>.
- Branch is fix/heavy-dr-citations (already checked out). Commit your work with conventional
  commits. Do NOT push, do NOT touch main.
- Heavy DR quota cap: <=5 calls total, short probe queries; prefer the FREE path above.
  A concurrent heavy run may be using the same ~/.codex/auth.json — prefer read-only
  conversation-detail GETs to avoid sentinel/token contention.
- Anti-hallucination: cite source file+line for claims; mark unverified items
  "(needs live test)"; do NOT fabricate field names — confirm them from captured raw data.

## Suggested sub-task order
1. (C1) add GPT2AGENT_RAW_DUMP raw dump to Phase 1 + Phase 2 of deep_research_heavy.
2. FREE-diagnose via conversation detail; save raw fixture; locate content_references.
3. (C2) fix _emit_done / _apply_path(/message/metadata) / _poll_dr_completion to extract
   refs from the correct node/key; add offline replay test.
4. (C3,C4) E2E heavy run (PYTHONPATH=worktree) + full suite; update CHANGELOG.
5. Write a short docs/goals/heavy-dr-citations-RESULT.md: root cause (H1/H2), the fix,
   evidence (refs count before/after), and any residual risk.
