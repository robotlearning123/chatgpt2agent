# Release team review

The final application candidate is `d6b9b63525635a5428f6d87e52909a2c8c9a0788`,
reviewed as a delta from preparation pin `cf928126`. Earlier full-candidate
reviews use base `e911a3a` and pin `cf928126`; those boundaries are preserved.
The owner requires one verified device. No merge, tag or publication is authorized.

## Findings addressed

The independent GLM reviewer reproduced stale assistant anchors accepting tool
patches, completion before trailing citations, lost pre-envelope text/references,
metadata continuations becoming progress text, and malformed auxiliary metadata
raising an attribute error. The primary reproduced the same failures before
accepting them. The implementation now tracks message roles, defers completion
until successful stream termination, preserves reordered text and references,
and ignores malformed heavy auxiliary metadata. Nine parser regression cases were
added; independent GLM replay demonstrated all nine failing on the prior parser.

The primary independently ran the final tree: **671 passed, 13 skipped**.
Original adversarial replay now preserves answer text and citations without
emitting a premature clean completion. Ruff, ShellCheck, release metadata and
diff checks pass. A live account/light-research selection passed **5/5**.

The strict heavy connector-start verification remains in place. Missing or
changed upstream verification fields can reject a run even if a report widget
exists. This availability limitation is deliberate: an unverified ordinary Chat
result must not be presented as verified heavy research. The error can indicate
missing verification, not necessarily an exhausted quota.

Package review also corrected historical artifact references and the doctor
exit-code description. A healthy bridge with only the legacy gate blocked can
return exit 0; neither doctor success nor an isolated MCP handshake proves live
research completion.

## Review accounting

Devin's first native tester independently ran the old candidate's full suite
(**655 passed, 13 skipped**). Its parent and the second-account parent terminated
on quota errors; their incomplete final reviews are not counted as acceptance.
Completed work was retained and the missing stages handed to the third account,
using native tester/verifier profiles pinned to `swe-2-high`.

Final lane verdicts, artifact acceptance and runtime CI are recorded in
`VALIDATION.json`. All dispatched review processes have finished. Raw local logs, account details,
and scratch reproductions remain private.

## Full-review findings and closures

Grok found that the MCP consumer preferred a completed clarification question
when a later explicit clarification-failure event revoked it. The consumer now
honors those flags. Two real registered-tool cases failed before the fix and
pass afterward; a completed-report positive control remains green.

Grok also reproduced rollback leaving stale editable metadata when the old
branch moved. Rollback now restores metadata while detached and preserves the
changed ref. Stable/moved/deleted tests pass; moved/deleted cases failed before
the fix. A further independent GPT-6.1 audit reproduced a late same-version
branch race. The final post-rollback checkout check prevents a false restored
receipt; its regression failed before and passes after d6b9b63. The primary
and integrity reviewer both executed the reproduction.

Devin's major continuation finding overlaps GLM F7. The primary reran Devin's
original three continuation probes and intervening-envelope prefix probe with
explicit assertions on the final source: all pass. Older FAIL/FIX-FIRST reports
remain evidence of defects found, rather than being rewritten as original passes.

## Final execution evidence

- Full regression: 671 passed, 13 skipped; no new skips.
- Final package lifecycle: 11 passed, 0 failed; fresh install, live account reads,
  30-tool MCP session, 9 manual schemas, handoff, 0.0.23 upgrade and uninstall.
- Primary installed candidate: 43 files match the final wheel; code and metadata
  both 0.0.24; dependencies and fresh isolated MCP pass.
- Real installed MCP light-research report: 1744 characters, official source,
  no tool error or incomplete flag, 22.68 seconds.
- New live stream tests: account/light 5/5; PONG/heavy 2/2 in 182.32 seconds.
  These used 9b3f483; stream code is identical through the final candidate.
- Final application/workflow d6b9b63 CI: 13 required jobs plus CodeRabbit success.

## Remaining bounded limitations

The reviewed light parser can still emit an empty clean result for a terminal
frame with no answer text. Aborted rounds omit captured references. Neither is
claimed as successful live research evidence. Heavy downgrade matching targets
the observed GPT slug family; unsupported non-GPT echoes and code-only tool
payloads are not newly validated by this release. The unchanged browser and
account-write paths retain the skip boundaries in ACCEPTANCE.md.

Fleet updates intentionally accept an explicitly supplied local reviewed commit;
origin/main ancestry is not required for an owner-authorized candidate rollout.
Dirty-tree, exact-pin, interpreter ownership, lock, verification and rollback
checks still apply. Using a symlink alias for CODEX_HOME can split local pacing
state; configured account homes should keep a consistent path.

## Final independent verdicts

Grok 4.7 accepted the full repair delta through 08cbdf3: **PASS**, 83 focused
passes, nine parser negative-control failures plus two clarification and two
rollback failures on the old code. Its independent foreign-ref probe confirmed
branch, tag and notes preservation. The later workflow-only d6b9b63 guard was
accepted by ccz/GLM (**PASS**, 15 tests and six independent Git scenarios) and
GPT-6.1 integrity review. GLM separately accepted the parser delta at 9b3f483
(**PASS**, 78 focused passes/6 live skips; nine old-code negative controls).
The primary's final execution verdict is **PASS** at d6b9b63.

The final archives were independently compared against the audited build:
every wheel/sdist entry and uncompressed byte matches. Final SHA256SUMS is
verified. The one-device acceptance gate is complete. The release is prepared
for owner approval; no merge, tag or publication has occurred.
