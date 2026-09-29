# Independent review receipt

Date: 2026-09-29. Writer: Codex (GPT family). Reviewer: ccz / GLM 5.3.

The configured cross-model review fallback was used after Grok and Devin
attempts stalled without substantive verdicts. Those attempts are retained
locally and are not counted as acceptance.

- Full source review: base `e911a3a` to `4e632bd`; independent pinned-export
  suite 639 passed / 13 skipped. Review reproduced an ordering defect in the
  heavy-research downgrade guard. The primary accepted and fixed it.
- Final delta review: `4e632bd` to `8460522`; verdict **PASS**, conditional on
  committing the sanitized preparation receipt before tagging. This receipt
  commit satisfies that condition.
- Independent final execution: 642 passed / 13 skipped; focused heavy/runner
  18 passed; Ruff and release metadata passed.
- Independent reproduction: seven scenarios passed on `8460522`. The same
  reproduction detected three expected failures on `4e632bd`: metadata-first
  false rejection, a later foreign connector clearing verified startup, and
  a final answer escaping before late downgrade metadata was checked.
- Primary execution agrees: full suite, package build/Twine, clean install /
  upgrade / MCP emulation (11/0), CI, and final live research all passed.

The reviewer did not execute live conversations or independently build the
packages. Its written report predates the final account-A live completion:
that run at `8460522` completed in 500.0 seconds after three transient polling
HTTP 500 errors. Earlier two-account heavy successes were at `895e5d1`.
Foreign-connector rejection was verified offline, not through a live foreign
connector request. This corrects an imprecise live/offline label in the local
review report; it does not alter the executed test results.

Non-blocking follow-ups: extract shared parser logic, improve provenance
mismatch diagnostics, and add the reviewer's verified-then-foreign scenario
to the permanent suite. No review condition remains for preparation. Tagging,
publication and fleet cutover still require the owner's separate decision.

Full reviewer logs, pinned exports, reproductions, failed attempts, and raw
run receipts remain in the private local release archive. They are excluded
from the public branch and distributions.

## Fleet workflow review, September 29

Independent reviewer: ccz / GLM 5.3; initial pin `ce33f03`, final pin `f46af68`.
Verdict: **PASS**. Initial full suite independently reproduced 651 passed /
13 skipped. Final focused suite: 11 passed. The primary final suite is 653/13.

Two low findings were fixed: wheel comparison now rejects unexpected installed
files (ignoring bytecode caches), and rollback requires code and distribution
metadata to agree. The reviewer reproduced both fixes with real execution,
including real git + offline pip + verifier subprocess rollback cases and a
consistent-version control that correctly records restoration. No new delta
findings. Application package bytes are unchanged across these workflow commits.

The deployment ordering review also identified shared editable registrations:
consolidate them before moving the shared clone. The local conda registration
was backed up and consolidated; no shared dependencies changed. A short
intermediate metadata mismatch occurred before consolidation and was resolved.
The corrected order is explicit in the runbook. Device/live-access evidence
is primary verification, separate from this independent code review.

## Final light dispatch correction

Pin `ba9201f`, range `5ae329f..ba9201f`. Independent ccz / GLM 5.3 verdict:
**PASS**. Targeted suite: 18 passed / 6 live skips. The reviewer reproduced
the two new regression failures on the old pin and their passes on the fix.
Adversarial replay checked malformed recipients, empty all-recipient code,
visible argument precedence, both observed dispatches, and no answer pollution.
The five-line runtime correction needs no further simplification. The heavy
smoke now exercises the actual connector, and the live environment flags match
the runtime's nonempty-string semantics. Primary full suite: 655/13; real
account/light selection 5/5 on each account; PONG/heavy completion 2/2.
