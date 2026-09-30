# Candidate installation rollout, 2026-09-29

Owner authorized updating existing installations. This is not release publication.
Inventory covered 15 account/OS environments across 12 physical devices.
Three environments had gpt2agent installed; 12 did not. No application was
newly installed in the latter environments. Windows/WSL checks were read-only;
WSL distributions temporarily started for inspection were returned to stopped.

| Environment | Installed candidate evidence | Remaining verification |
|---|---|---|
| Primary Linux | 0.0.24 code/metadata; application ba9201f; workflow f46af68; 43 wheel files; MCP 30 tools / 9 manual schemas / handoff pass | 11 pre-update MCP processes remained at the final snapshot; require client reconnect; owner jobs preserved |
| Secondary Linux | Upgraded 0.0.14 to 0.0.24, latest ba9201f wheel; dependency check and identical isolated verification pass | Live doctor reports 401 expired token; owner must renew login before live acceptance |
| macOS | 0.0.24 at ce33f03; dependency check and identical isolated verification pass | SSH unreachable after final workflow follow-up; inspect existing receipt and checkout before retry; newest ba9201f fix not yet installed |

The primary host's obsolete conda editable registration was backed up, removed,
and replaced with a CLI forwarder to the verified primary venv. Shared conda
dependencies were not modified. New primary processes use the candidate;
existing MCP clients were not killed or silently counted as refreshed.
Both primary accounts' live doctor: 24 OK, 0 failed, 1 blocked legacy gate,
4 unverified writes. Secondary Linux's failed live doctor is not a package
installation failure, but prevents claiming full end-to-end fleet readiness.

Full device paths, process identifiers, backups, incomplete transaction records,
and logs remain in private local rollout artifacts. On macOS reconnect, read
the existing final-update receipt and inspect HEAD, working tree, installed
code and metadata before resuming; do not overwrite or rerun an incomplete
transaction blindly. No tag, merge, publication, or owner-session restart occurred.

Current candidate ba9201f is verified on two of the three installed environments.
The Mac's earlier 0.0.24 version string is not evidence of the latest package bytes.

## Owner-revised release acceptance

The owner explicitly instructed "one device verify is fine". Primary Linux
is the accepted device: ba9201f installed package, all 43 wheel files, matching
code/metadata, dependency health, fresh MCP 30 tools / 9 manual schemas and
manual handoff pass. This satisfies the device gate for release preparation.
Mac connectivity, secondary account renewal and old-client reconnect remain
operational follow-up, not blockers to preparing this release.
