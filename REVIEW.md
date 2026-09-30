# Code review rules (gpt2agent)

Repo-specific always-check rules for `/my-review`, `/code-review`, `/simplify`,
and any independent reviewer. Every line here traces to a confirmed incident.

## Merge gate

The owner accepts independent cross-model verification in place of a second
human approval. Before merging, the responsible agent must verify:

- A reviewer from a different model family has inspected the committed change,
  with a recorded PASS, commit/range, model identity and execution evidence.
  Re-review subsequent changes; a stale verdict does not cover new code.
- The primary has independently checked the result, completed simplification,
  and closed all blocking findings and review discussions.
- Required CI passes on the current PR head, which is up to date with main.

GitHub requires the PR, required checks and resolved discussions, with zero
required approving GitHub reviews. Cross-model evidence is a workflow gate
checked by the responsible agent; a green CI badge alone does not establish it.
Merge normally with the verified head pinned; do not bypass CI or branch rules.
Release publication still requires the owner's explicit authorization.

## Always check

- **A dependency pin is a claim about the environment.** Code must not assume the
  installed version of a pinned dependency: an out-of-range install has to fail
  loudly or be adapted to — never crash at startup, never be silently ignored.
  *(2026-09-23: `mcp` 2.2.0 left in a venv outside the `mcp>=1.27,<2` pin made
  `gpt2agent run` die at startup for every stdio MCP client, for days.)*
- **Optional kwargs of third-party constructors are version-dependent.** Gate
  `host`/`port`-style arguments on the installed signature instead of passing
  them unconditionally; if the SDK moved them elsewhere, refuse loudly rather
  than silently serving a default.
- **"Works with X and Y" requires an executed check per variant.** Import-level
  compatibility is not behaviour compatibility — the same incident had a working
  import shim and a crashing server path.
- **Test the call site, not only the helper.** A fully tested helper does not
  stop a regression at its caller.
- **Hand-written docstrings can claim mechanisms that do not exist** ("the skill
  pre-approves all N MCP tools" claimed an allowlist no code implements).
  Verify the mechanism, then the wording.

## Verification bar

- Blocking findings must be reproduced by execution on a scratch copy before
  being confirmed; prose-only reviews are drafts.
- Live-network tests flake on this host (DNS): rerun once before treating a
  failure as real, and record which run the verdict came from.
- Power-test every negative claim: show the check can produce a positive
  (disabled-vs-enabled, or a known-positive input).

## Self-review and closeout loop

Self-review, testing and improvement are part of every task, without a separate
owner reminder. Inspect the actual diff and result, reproduce valid defects,
make bounded fixes, and run checks that exercise the failure as well as success.
After fixes, obtain the cross-model review above, simplify the final diff, and
clean only this lane's temporary files, processes and finished worktrees.
Close only after checking the actual merged, published or installed state against
the requested scope. Preserve failed attempts and verification receipts; label
historical evidence and operational follow-ups separately from completed work.
Record improvements that need broader scope rather than silently expanding the
task or modifying an already published artifact.

## Skip lists

- Lockfiles, `dist/`, `build/`, `gpt2agent/_vendored/`, the generated
  `QA_REPORT.html`, and anything CI already gates (`ci.yml`).
- **Workflow files are never skipped**: `.github/workflows/release.yml` runs
  only on a version tag, so nothing else validates it before it can break
  publishing, permissions, or the release gate.

## Nits

- Cap nit-level findings at five per review; wording nits in docs are optional.
- `docs/dev/specs/**` is a historical design record — do not request rewrites there.
