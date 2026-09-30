# Release acceptance audit

Candidate application and test pin: `ba9201f`. This audit supplements the
verification history; it does not authorize publication.

The owner explicitly revised device acceptance to **one verified device**
("one device verify is fine"). The primary Linux installation satisfies that
gate: current candidate bytes, code/metadata, dependencies, fresh isolated MCP
and account-level live evidence. Other fleet work remains recorded but is not
a release-preparation blocker. Status: **ready for owner release approval**.

| Requirement | Evidence | State |
|---|---|---|
| Current ChatGPT compatibility | September 29 compatibility report; live model-routing receipts | Verified with documented Work/Codex versus Chat boundary |
| Regression coverage | 655 passed, 13 skipped; all 13 CI jobs passed on ba9201f | Pass |
| Light research on both accounts | Live account/light test selection: 5 passed on each account; completion, tool events and citations asserted | Pass |
| Heavy research completion | Current connector completion test plus PONG: 2 passed in 152.69 seconds; prior two-account MCP receipts retained | Pass |
| Tool dispatch regression | Sanitized live wire structure; web/web.run nodes had hidden arguments; two regression cases now preserve recipient events | Pass |
| Packaging and first-user lifecycle | New ba9201f wheel/sdist; Twine; no raw captures/JWT-shaped values; outsider 11 passed / 0 failed | Pass |
| Health and README boundaries | Both primary doctors 24 OK / 0 failed / 1 blocked legacy gate / 4 unverified; README distinguishes gate checks from executed tools | Pass with stated limits |
| Manual fallback | Isolated handoff with zero network; 9 schemas checked; live conversation gate is open through bridge | Pass for applicable fallback check; no new human browser roundtrip |
| Independent review and simplification | Independent GLM PASS at ba9201f; 18 targeted passes, negative control and adversarial replay | Pass |
| One-device acceptance (owner-revised scope) | Primary Linux ba9201f; 43 package files match built wheel; metadata, dependencies and fresh MCP pass; live evidence above | Pass; other fleet work tracked separately |
| Publish preparation | 0.0.24 manifests/changelog; draft PR #87; proposed annotated tag v0.0.24 | Prepared; no merge/tag/publish authorized |

The 13 default skips are one live account test, three light-research tests,
three SSE tests, three browser tests and three account-write tests. The
account/light selection and two SSE cases were run separately. The remaining
heavy metadata-only case overlaps the completed connector/MCP verification;
the unchanged browser and account-write paths retain their documented limits.
We did not overwrite account instructions, add account memory, or create a
Codex task in another repository just to turn skipped tests green.

Initial supplemental live attempts failed because conftest disables the bridge
and any nonempty OFF value (including 0) keeps it disabled. Correctly enabling
the bridge exposed a real missing-tool-event regression (4 passed / 1 failed).
The sanitized stream showed dispatch recipients with empty bodies. After the
fix, both accounts passed 5/5; the failure history is retained privately.
