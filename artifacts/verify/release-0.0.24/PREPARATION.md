# v0.0.24 release preparation

Date: 2026-09-29. Base: `e911a3a` (published v0.0.23).
Candidate branch: `release/v0.0.24`.
State: release prepared, not tagged or published. Owner-authorized candidate
installation updates are recorded in `ROLLOUT.md`; runtime acceptance remains
partial because a device is offline, another needs login, and old clients need reconnect.

## Scope

Source changes from PR #83 (`42d8142`) and PR #86 (`92baad8`), plus temporary-chat
handoff recovery (#84), the September 29 compatibility report, and safe
release emulation. Source was applied to a clean base rather than merging
PR history: raw research captures contained 12 distinct expired JWT-shaped
values (expiry decoded locally; signatures not verified). Those captures
and the original integration worktree remain in a private local archive;
none are included in the release branch or built distributions.

The separate MCP 2 migration, voice, and Grok-account feature branches are
not part of this maintenance candidate. No project dependencies or GitHub
Actions workflows changed.

## Model evidence

Official sources: `docs/chatgpt-update-2026-09-29.md`.
Both live Pro catalogs exposed 24 entries including `gpt-6.1-sol-wm`.
Two completed Chat routing checks on account A requested `gpt-6.1-sol-wm`
and `gpt-6.1-sol`; both resolved to `gpt-5-6` and returned a Model note.
This does not establish GPT-6.1 execution through this project's Chat backend.
The default stays `gpt-5-6`; Codex/Work model selection is separate.

## Verification

- Integrated baseline: 632 passed / 13 skipped.
- Temporary recovery fix: 637 passed / 13 skipped.
- Final ordering correction (`8460522`): 642 passed / 13 skipped. Skips are the explicit
  live/browser/destructive-write tests; bounded live checks are listed below.
- Ruff, ShellCheck on changed shell scripts, `git diff --check`, and release
  metadata validation for proposed tag `v0.0.24`: pass.
- Clean wheel/sdist build and Twine validation on `8460522`: pass.
  Wheel has 50 files; source archive has 59. No raw taskruns or JWT-shaped
  values are present; hashes are in `SHA256SUMS`.
- Outsider emulation rebuilt from `8460522`: 11 passed / 0 failed. Includes clean install, version,
  no-token doctor, isolated client registration, live doctor, real stdio MCP
  (30 tools, manual parameter on all 9 conversation tools), account and
  conversation reads, zero-network manual handoff, v0.0.23 upgrade, uninstall.
- Doctor on both accounts: 24 OK, 0 failed, 1 blocked legacy gate,
  4 unverified writes/file operations. Bridge mint succeeded. An open gate
  does not prove each conversation feature completed.
- Fresh light research: A 16.7 s / 1197 chars; B 14.6 s / 1335 chars.
- Heavy research with the initial imported guard failed on both accounts
  (A 14.8 s; B 30.7 s): it misclassified the outer `gpt-5-6-instant` model.
- Historical successful-run metadata plus an executable negative control
  reproduced that defect on `7eadbdc`. On `895e5d1`, a verified Deep Research
  startup permits that outer slug; a foreign connector still raises. The
  completed widget's provenance and completion checks remain mandatory.
- Corrected heavy research: A completed in 142.4 s / 1932 chars; B completed
  in 260.5 s / 1374 chars. Both returned report text with source links.
- Final commit `8460522` heavy recheck on account A: completed in 500.0 s /
  1599 chars after three transient HTTP 500 poll errors. No duplicate request
  was sent. This records successful recovery, not a latency guarantee.

The first emulation stalled downloading through the host package index.
A public-PyPI rerun exposed a harness file named `mcp.py` shadowing the
installed package; renaming it to `mcp_smoke.py` produced the 11/0 result.
All attempts are retained locally; only sanitized summaries are tracked.
The final stream-ordering correction validates the resolved model after all
startup frames and before releasing a completion. Regressions cover both
startup/metadata orders, foreign connectors, and late downgrade metadata.

The simplification pass removed the duplicate heavy-only runner; one runner
now serves both research modes, and its five safety tests pass unchanged.

## Review and publication gate

Independent GLM 5.3 review passed the final code at `8460522` and independently
reproduced 642 passed / 13 skipped. See `REVIEW.md` for findings, fixes, and
review boundaries; `VALIDATION.json` and `SHA256SUMS` record the final evidence.
Grok and Devin attempts stalled without substantive verdicts and are not
counted as acceptance. The reviewer required this sanitized receipt to be
committed before tagging; it is included in the preparation commit.

The release runbook requires explicit owner approval before pushing
`v0.0.24`, since the tag triggers publication. Preparation does not authorize
that action. The owner separately authorized updating existing device installations to the
verified candidate. This does not authorize tagging or publication.

## Workflow and deployment follow-up

Final workflow code: `f46af68`. Primary full suite: **653 passed / 13 skipped**.
Independent GLM review: PASS; 651/13 on the initial workflow and 11/11 targeted
tests on the final fixes. The reviewer independently executed real git/pip
rollback cases and installed-file rejection. See `REVIEW.md`.

Fleet sync now previews by default, pins a commit, rejects dirty or foreign
installations, records an exclusive receipt, refreshes editable metadata, and
verifies rollback code plus metadata. Installed verification uses isolated
Python outside the checkout, compares every package file to the wheel, rejects
extra files, and checks MCP tools/manual schemas with networking disabled.
Shared editable registrations must be consolidated before moving their clone.

The rebuilt candidate at `ce33f03` passed outsider emulation (11/0); application
package bytes are unchanged through `f46af68`. `SHA256SUMS` identifies this build.
Final code CI: all 13 required jobs passed, plus CodeRabbit success.
Three existing installations passed version, metadata, 43-file wheel comparison
and isolated MCP checks. See `ROLLOUT.md` for live-access and reconnect limits.
