# Release validation

Runbook for validating a gpt2agent release before tagging. Archive every
receipt under `artifacts/verify/` so the run is auditable later.

Before expensive live or install checks, inspect active PRs/worktrees and the
actual merge requirements. Record the reviewed source commit, acceptance scope,
cross-model verdict and existing owner authorization. Finish source changes and
review first; later changes invalidate only the evidence they affect. Compare
the merged tree with the reviewed tree before choosing the release tag target.

Keep one current status receipt pointing to immutable per-attempt evidence.
Refresh it after each stage completes; do not leave preparation status looking
current after publication. Apply the self-review/test/improve/closeout loop in
[REVIEW.md](../REVIEW.md) to both the product and this release workflow.

## 1. Pre-release health check

```bash
gpt2agent --version
gpt2agent doctor | tee artifacts/verify/doctor-$(date +%Y%m%d).txt
```

Record the version and date in the release notes. Expect read-only rows to
report OK; rows for tools blocked by the upstream Sentinel/Turnstile challenge
must be compared with the previous release; investigate newly changed rows.
`doctor` exits 0 when checked surfaces are healthy, including when only the
legacy gate is blocked and the bridge is OK. Other failed or blocked rows
produce exit 1; exit 2 means no token. A known upstream blockade with zero
failures can be recorded as a limitation, but does not prove live conversation
completion. Any failed row blocks live acceptance until its cause is diagnosed.

## 2. Manual-handoff roundtrip

While `/backend-api/conversation` is blocked, verify the Phase 0 fallback
end to end exactly once:

1. Call `chat("release check", manual=True)` and confirm it returns a JSON
   handoff (`status: "manual_handoff"`) with zero network calls.
2. Paste `prompt` into chatgpt.com by hand and send it.
3. Read the reply back with `list_conversations` → `get_conversation`.

Save the handoff JSON and the fetched conversation under
`artifacts/verify/` as the roundtrip receipt.

## 3. Regression

```bash
pytest -q | tee artifacts/verify/pytest-$(date +%Y%m%d).txt
```

Must be fully green — 0 failures, no new skips versus the previous run.

The default suite deliberately disables live calls and the Sentinel bridge.
To exercise the current Chat/research paths on an authenticated, bridge-enabled
host, use an explicit live selection and keep production pacing enabled:

```bash
SKIP_LIVE=0 GPT2AGENT_SENTINEL_BRIDGE_OFF= GPT2AGENT_RATELIMIT_OFF= \
  pytest -q tests/test_backend_tools.py tests/test_deep_research.py \
  tests/test_sse.py::test_sse_pong
```

The `*_OFF` switches use nonempty-string semantics: `0` still disables the
feature. Empty values override the offline defaults in `tests/conftest.py`.
For the heavy completion test, additionally set `SKIP_HEAVY_DR=0` and select
`tests/test_sse.py::test_sse_deep_research_heavy`. It must return the report,
not just acknowledge startup. These calls consume account quota and retain
normal pacing. Archive failures as well as successful retries; distinguish
harness configuration errors from upstream or application failures.

## 4. Blocked-tool annotation check

The README tool-status table must match the `doctor` output from step 1
row-for-row. If `doctor` reports a tool newly blocked or newly working,
update the README table in the same release — do not ship a stale status.

## 5. Artifact outsider emulation (added 2026-09-15, v0.0.14)

Exercise the BUILT artifact the way a first-time user would — build, wheel
install into a clean venv, no-token first run, client registration with an
isolated HOME, a real MCP stdio client session (tool schemas + live
read-only calls + a `manual=True` handoff), the previous-release→candidate upgrade path,
and uninstall cleanliness:

```bash
scripts/release-emulation-test.sh <release-worktree> | tee artifacts/verify/human-emulation-$(date +%Y%m%d).log
```

Must end `RESULT: N passed, 0 failed`. Introduced after v0.0.14's first cut
caught a missed `.claude-plugin/plugin.json` version bump and a test-harness
stdio flag error before they reached users.

Check that the chosen build interpreter has `build` and `twine` before starting.
Keep dependency caches enabled for normal clean-environment installs: a clean
venv does not require downloading every dependency again. If a newly published
version is missing from the package index, retain the failure, verify the PyPI
version JSON and allow index propagation before retrying. Use cache bypass only
to diagnose a stale index, then restore normal caching. Verify downloaded public
wheel/sdist hashes against the CI artifacts; a local rebuild has different
archive hashes and must not substitute for the published files.

## 6. Owner publish gate (added 2026-09-15 — mandatory)

Before the publish step runs (tag push triggers `release.yml` automatically,
so this gate sits BEFORE tagging), present the owner a release summary:
version, CHANGELOG highlights, CI state, runbook receipts (steps 1-5), and
the planned tag. **Do not push the release tag until the owner explicitly
approves.** If a publish run fails and a rerun would retry the publish step,
the same approval applies to the rerun. A repo rename additionally requires
migrating the PyPI trusted publisher to the new repository path FIRST.

## 7. Post-tag verification (added 2026-09-18 — mandatory)

A pushed tag only STARTS the publish; verify it actually landed:

```bash
gh run list --repo robotlearning123/gpt2agent --branch vX.Y.Z   # Release run must go green
gh release view vX.Y.Z --repo robotlearning123/gpt2agent        # release + assets exist
pip index versions gpt2agent 2>/dev/null || curl -s https://pypi.org/pypi/gpt2agent/json | python3 -c 'import json,sys;print(json.load(sys.stdin)["info"]["version"])'
```

Report PyPI version + GitHub Release URL; do not claim published on tag
push alone. If the run fails, read the job log before rerunning.

## 8. Fleet sync + cleanup (added 2026-09-18 — mandatory)

The fleet does NOT run the dev worktree — it runs the `gpt2agent` binary,
which resolves to `~/.local/share/gpt2agent-venv` (editable install → the
clone at `/home/robot/workspace/47-chatgpt2agent/gpt2agent`). Merging to main
without syncing that clone is exactly how the fleet ended up running ~v0.0.14
on 2026-09-18 while the fix sat in a worktree. For an owner-authorized local candidate rollout, pin the reviewed commit; do not
use a moving branch as the verification identity. A local rollout does not
create a public release. After an approved merge, pin the merge commit instead.

Preview first (the command never applies by default):

```bash
scripts/fleet-sync.sh <reviewed-sha> --version 0.0.24 \
  --python "$HOME/.local/share/gpt2agent-venv/bin/python" \
  --receipt "$HOME/.local/state/gpt2agent/preview-unique.json"
```

Before moving a shared clone, inventory every attached editable installation.
Include each interpreter in the update, or back up and consolidate an obsolete
registration first, so an omitted environment cannot silently change code
while retaining old metadata.

Repeat `--python` for each editable installation attached to that clone; set
`--clone` for a different device/path. Inspect the preview, then repeat with
`--apply` and a **new** receipt path. The updater refuses dirty or concurrently
changed clones, resolves the ref once, refreshes package metadata without
upgrading dependencies, and checks version, import location, CLI and fresh MCP
startup. Failed verification attempts to restore the prior checkout and
attempted installs; a failed rollback is explicitly recorded. An interrupted
run leaves an `incomplete` receipt and a lock: inspect before retrying, never
blindly remove an existing lock. Receipts are private and never overwritten.

For wheel/uv/pipx installations, use that installation's package manager and
the exact verified wheel, retaining the prior version for rollback. Verify
outside the source checkout with the target Python:

```bash
/path/to/target/python -I scripts/verify_install.py --version 0.0.24 \
  --wheel /path/to/verified/gpt2agent-0.0.24-py3-none-any.whl --mcp
```

`-I` prevents checkout/PYTHONPATH shadowing. Both code and distribution metadata
must match; `--wheel` also compares installed package bytes. The fresh MCP
check uses an unauthenticated temporary home, checks 30 tools and 9 manual
schemas, and exercises a zero-network manual handoff. It does not prove live
account authentication or research completion: retain separate account-level
live receipts. Check dependency health with the installation's package manager;
do not repair an unrelated shared environment by silently changing its packages.

A rollout receipt must list every inventory target separately: verified,
not installed, unreachable, failed, or reconnect pending. Check Windows and
WSL separately. Update one canary before other devices. Existing stdio MCP
processes keep loaded code until their owning clients reconnect; do not count
a new-process check as proof that old sessions restarted. Do not terminate
active research jobs or unrelated client sessions. Recheck the command path,
package metadata, exact package bytes, and MCP startup on each updated device.

Then clean up, in the same release session — not "later":

- `git worktree list` → remove finished worktrees (`git worktree remove`);
  stale branches stay recoverable, uncommitted work does not — check
  `git status --porcelain` inside each before removing.
- `git push origin --delete <merged-branch>` for the merged feature branch.
- Repoint any editable install that referenced a removed worktree
  (`pip install -e <clone>` or `pip install gpt2agent==<released>`).
- Kill leftover background shells/watchers started during the release.
- Keep `artifacts/verify/` receipts — never delete those.
