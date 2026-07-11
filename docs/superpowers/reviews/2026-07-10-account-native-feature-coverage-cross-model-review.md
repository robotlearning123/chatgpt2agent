# gpt2agent 0.0.12 account-native coverage: cross-model review

- **Date:** 2026-07-10 EDT
- **Baseline design commit:** `36ab2b9d87652403a9f89b573aee0a7a0241b17e`
- **Original reviewed design SHA-256:** `fc8a3fff4f32d70671d944bf6851b5fa31f6ae7cd1004659030c2ba1e8d24b31`
- **Amended normative review SHA-256:** `9ae60793e9421d946894dbd480d89d7b1ca4d5cd8e30de1fb36c8d9b25a96f58` (63,473 bytes)
- **Approved-file SHA-256:** `3ca3f0b9db7b2fce53056a3bb754eb084b35cafc1d918c345c2f2e931751e979` (63,459 bytes)
- **Approved-file diff SHA-256 against baseline:** `d89a8816244ba7a549ed7d00a389eb8f46b6656c6ef69106a3238914ddf142cc`
- **Original exact-design verdict:** PASS after corrections
- **Amended exact-design verdict:** zero blockers from Grok 4.5, GLM-5.2, and Claude Opus 4.8
- **Current review status:** complete; approved for TDD implementation
- **Implementation/release status:** v0.0.12 approved for implementation with all Voice code moved to v0.0.13

On 2026-07-10 the user narrowed v0.0.12 to exclude the Voice catalog and
assigned that adapter to v0.0.13. The original PASS was not reused. Three fresh
reviewers independently examined the complete amended file at the exact
normative hash above after the release-audit corrections were applied.

After those runs, the first metadata line changed from “amended re-review
pending” to “review complete; approved for TDD implementation.” That
administrative status-only change produced the approved-file hash above; no
normative requirement changed. The reviewed hash and the current file hash are
both retained so the evidence boundary is explicit rather than silently
claiming the reviewers saw a later byte sequence.

## Amended exact-design re-review

| Lane | Exact runtime/model | Isolation | Result | Blockers |
| --- | --- | --- | --- | ---: |
| Grok | Grok CLI `0.2.93` (`f00f96316d`), `grok-4.5` | verbatim input; web, memory, subagents, plan, tools, and MCP disabled | `PASS` | 0 |
| CCZ | `ccz` -> Claude Code `2.1.206`, explicitly routed to `glm-5.2` | no Chrome/session persistence/slash commands/tools; strict empty MCP and hooks/plugins | `PASS_WITH_CHANGES` | 0 |
| Opus | `cc2` -> Claude Code `2.1.206`, `claude-opus-4-8`, account-2 OAuth | low effort; no Chrome/session persistence/slash commands/tools; strict empty MCP and hooks/plugins | `PASS` | 0 |

The compact findings below normalize wording for the durable review record; the
verdict and blocker arrays are unchanged from the exact model outputs:

```json
{"model_claim":"amended-0.0.12-account-design-rereview","verdict":"PASS","blockers":[],"nonblocking_findings":["installed_plugins false inheritance is currently unreachable because the Plugin catalog has no explicit false rule","capability probes must reuse the same strict envelope validators as their tools","unnamed automation or memory flags must remain null until reviewed"]}
{"model_claim":"9ae60793e9421d946894dbd480d89d7b1ca4d5cd8e30de1fb36c8d9b25a96f58","verdict":"PASS_WITH_CHANGES","blockers":[],"nonblocking_findings":["make the installed-Plugin item bound explicit in implementation","retain strict required release handling for the current Plugin envelope","the USER probe does not prove WORKSPACE-only Plugin entitlement","keep public_bundle_only grounded in the checked-in evidence matrix","execute serial probes in normative table order"]}
{"model_claim":"claude-opus-4-8","verdict":"PASS","blockers":[],"nonblocking_findings":["fail closed if a root-array Plugin catalog exceeds the JSON bound","use a bounded per-probe timeout inside the 90-second aggregate budget","compute the Plugin catalog record before installed-Plugin inheritance"]}
```

The non-blocking findings are implementation assertions, not permission to
weaken the design. In particular, the implementation must run the normative
probe table top-to-bottom, reuse each adapter's exact validator, treat absent
unnamed feature flags as null, cap an unpageable installed-Plugin response, and
preserve USER versus WORKSPACE evidence scope.

The final successful runs took approximately 44.8 seconds (Grok), 142.1 seconds
(GLM), and 15.2 seconds (Opus). The first final-hash Opus attempt used maximum
effort and hit the 210-second hard timeout without output; it was excluded. A
bounded low-effort retry succeeded. The default Claude account was also
excluded after its organization policy refused subscription access. Earlier
results on the superseded `77a6bc...` and `cf5269...` hashes, an interrupted CCZ
run, and truncated harness streams were not counted. No result was relabeled as
another model, no reviewer accessed the account or repository through tools,
and no reviewer artifact or process remained afterward.

## 1. Scope and evidence boundary

This review tested the design for an MCP server that uses an authenticated consumer `chatgpt.com` account, not the OpenAI API. It covered:

- current ChatGPT and Codex product changes;
- the real signed-in account and deployed website surface;
- public web-client bundle evidence;
- private adapter behavior already present in this repository;
- MCP and Skill design, security, performance, CI/CD, release, and cleanup;
- the specific feasibility of exposing GPT-Live through MCP.

The review kept four facts separate:

1. OpenAI officially documents a product feature.
2. The public ChatGPT web client contains a route or field marker.
3. A read-only request reaches that route for this account now.
4. gpt2agent safely exposes the feature through a packaged MCP contract.

No reviewer was allowed to treat one fact as proof of another.

## 2. Original pre-amendment reviewer provenance

| Lane | CLI and model | Isolation | Initial result | Final result |
| --- | --- | --- | --- | --- |
| Grok | Grok CLI `0.2.93`, explicitly selected `grok-4.5` | one turn, no memory, subagents, web, tools, or account access | `PASS_WITH_CHANGES` | `PASS` |
| CCZ | Claude Code-compatible CLI `2.1.206` routed to `glm-5.2`; model usage confirmed `glm-5.2` | no tools, web, files, or account access; structured output captured in an owned temporary directory and deleted | `PASS_WITH_CHANGES` | `PASS` |
| Opus | Claude Code `2.1.206`, `CLAUDE_CONFIG_DIR=/home/robot/.claude-cc2`, explicitly selected `claude-opus-4-8` | tools, MCP, Chrome, slash commands, web, account access, and session persistence disabled | `PASS_WITH_CHANGES` | `PASS` |

The final Opus micro-review examined the current exact numbered excerpts, completed in 30.999 seconds, and reported zero web requests, permission denials, or tool calls. The final Grok micro-review completed in about 22 seconds. The final CCZ micro-review returned `PASS` and recorded only `glm-5.2` in `modelUsage`.

Model output was treated as a draft review, not as evidence by itself. Every accepted finding was rechecked against the current design, repository source, official documentation, or installed dependency source before amendment.

### Excluded harness attempts

The following attempts were not counted as cross-model evidence:

- the default Claude profile failed with exact error `403 oauth_org_not_allowed`;
- an early Opus wrapper was allowed too much repository context and crawled `.venv`; it was stopped and discarded;
- an early CCZ full review produced an oversized event stream whose final answer was truncated;
- one completed CCZ run was discarded after the local JSON extractor selected the wrong array shape.

No result was silently relabeled as another model. No raw reviewer stream was retained.

## 3. Accepted findings and design corrections

### 3.1 Catalog access is not feature execution

The original design allowed a successful model-catalog GET to make Agent mode, Code Interpreter, Canvas, image generation, and Deep Research look reachable. All reviewers agreed this was an overclaim.

The final design now:

- separates `chat_models` catalog access from those execution capabilities;
- allows explicit catalog advertisement to inform entitlement only;
- keeps execution `reachable_now: null` and `reachability_scope: "none"`;
- preserves typed failure status from a shared catalog request without copying catalog reachability into execution records;
- maps every capability to a deterministic `surface` and `reachability_scope`.

### 3.2 Voice catalog, transcript, and GPT-Live are different contracts

The first draft combined the voice catalog and post-session transcript under stable coverage. Official Voice documentation proves that a transcript is added to chat history, but it does not prove the private gpt2agent conversation adapter correctly handles the current Voice content shape.

The final design therefore:

- assigns the read-only voice catalog to 0.0.13 rather than 0.0.12;
- records post-session transcript access as inventory-only, deferred, and `unverified`;
- does not start Voice or read a conversation body in the required GET-only live gate;
- does not expose GPT-Live audio as a supported MCP capability.

### 3.3 Concurrent Session use needed a narrower correction

One early review characterized the shared `curl_cffi.Session` as generally unsafe across threads. That statement was too broad.

Independent verification against `curl_cffi 0.15.0` established:

- the official Session API describes Session as thread-safe but recommends a separate Session per thread;
- the implementation supplies a thread-local Curl handle;
- the real project risk is concurrent mutation and later reading of shared `Session.headers`, especially Authorization;
- connection caches are per thread, not one shared cross-thread pool.

The final design keeps the existing Session but removes Authorization from mutable shared defaults. Every authenticated request receives a fresh, complete header snapshot produced under the token lock. GET, POST, SSE, and Sentinel paths must use the same helper, and forced-overlap tests gate concurrent fan-out. Serialization remains the fail-safe default if isolation is not proven.

Official dependency references:

- [curl_cffi 0.15.0 Session API](https://curl-cffi.readthedocs.io/en/v0.15.0/api.html#curl_cffi.requests.Session)
- [curl_cffi 0.15.0 Session source](https://github.com/lexiforest/curl_cffi/blob/v0.15.0/curl_cffi/requests/session.py)
- [libcurl thread safety](https://curl.se/libcurl/c/threadsafe.html)

### 3.4 Public radar success cannot prove private adapter health

The final workflow is explicitly a **public-surface drift radar**. A green run means only that selected official-document fingerprints and public bundle markers remain present. It records account-contract and private-adapter status as `not_checked` and never implies account entitlement, route reachability, release readiness, or a live `reachable_now` value.

### 3.5 Local and release artifacts need separate identities

The local live gate exercises packages built from the reviewed checkout. The tag-triggered OIDC workflow independently rebuilds packages for publication. Their hashes need not match unless reproducible builds are separately designed and proven.

The final design uses:

- `local_candidate_artifacts` for the exact local package exercised by the account gate;
- `release_workflow_artifacts` for the workflow files compared with PyPI;
- explicit commit, tree, origin, filename, and SHA-256 identity for both sets.

### 3.6 Work identifiers are not general chat slugs

Work model identifiers remain opaque and Work-only unless the exact slug independently appears in the general model catalog. `chat` and `agent` reject a known Work-only slug as unsupported, and only the general-catalog record may drive `thinking_effort` validation.

### 3.7 Empty collections prove route shape, not item shape

The live account returned valid empty automation and Site collections. That proves route/envelope behavior only.

The final universal `item_contract_status` field has deterministic rules:

- `live_verified` only after at least one live item passes the normalized minimum schema;
- `public_bundle_only` when approved public-bundle or redacted evidence grounds the item schema and the synthesized fixture passes;
- `unverified_live` when neither populated-item condition is met;
- `not_applicable` for the explicitly defined non-collection capabilities.

### 3.8 Legacy security escape hatches require complete migration

The original migration language did not inventory every current `GPT2AGENT_ALLOW_REMOTE` and `GPT2AGENT_RAW_DUMP` reference. The final design removes the active remote bypass and raw dump, updates current user guidance, preserves immutable history, and defines separate exact final-search allowlists. `GPT2AGENT_RAW_DUMP` may remain only as a fail-closed runtime guard plus history/migration/design and negative tests; it may not remain as an active dump path.

## 4. Findings narrowed or rejected

- **Rejected:** a blanket claim that `curl_cffi.Session` cannot be used concurrently. The handle implementation is thread-local; shared mutable configuration was the specific unsupported assumption.
- **Narrowed:** the first public-radar draft did not literally claim private health, but its result namespace was ambiguous. The final naming and `not_checked` fields remove that ambiguity.
- **Rejected:** renaming the existing chat tool error merely because the capability status table also contains the string `unsupported`. They are distinct typed shapes and changing the project-wide error taxonomy would be unrelated churn.
- **Clarified:** `reachable_now: true`, `entitled: false`, and `status: "unavailable"` is valid only when `reachable_now` describes successful reachability of the exact route scope, not product usability.

## 5. Official and live product evidence

Official pages checked for the July 8–9 product change set:

- [ChatGPT release notes](https://help.openai.com/en/articles/6825453-chatgpt-release-notes)
- [ChatGPT Voice](https://help.openai.com/en/articles/20001274)
- [ChatGPT Work](https://help.openai.com/en/articles/20001275)
- [ChatGPT Sites](https://help.openai.com/en/articles/20001339)
- [Plugins in ChatGPT and Codex](https://help.openai.com/en/articles/20001256-plugins-in-chatgpt-and-codex)
- [Codex changelog](https://learn.chatgpt.com/docs/changelog)
- [Codex best practices](https://learn.chatgpt.com/guides/best-practices)
- [Build Skills](https://learn.chatgpt.com/docs/build-skills)
- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Python SDK releases](https://github.com/modelcontextprotocol/python-sdk/releases)
- [MCP authorization guidance](https://modelcontextprotocol.io/docs/tutorials/security/authorization)
- [MCP security best practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)

The July 8–9 snapshot includes GPT-Live-1/mini; ChatGPT Work and Scheduled Tasks; the Plugin Directory naming/distribution change; the unified desktop Chat, Work, and Codex app; Sites public beta; and retirement of new group-chat creation. The July 9 Codex changelog also records CLI 0.144.0/0.144.1, including interactive MCP authentication without an experimental flag, a `writes` app-approval mode, runtime host authentication, and installer/Code Mode reliability fixes.

The active host commands `codex`, `cx`, and `cx2` all report `codex-cli 0.144.1`. A separate global npm installation still contains `@openai/codex@0.142.4`, but it is not the executable resolved on `PATH`; it is an environment-hygiene item, not a project or release blocker, and was not uninstalled without authorization.

As of July 10, the official MCP Python SDK identifies v1.x as the current stable line, marks v2 as an alpha/beta pre-release, and recommends an upper bound below v2; the latest-release endpoint lists v1.28.1 as the current stable release. This validates the design's `mcp>=1.27,<2` compatibility constraint: `>=1.27` is the supported floor, not a claim that v1.27 is newest. The current MCP authorization and security guidance also supports the design boundary: local stdio may use environment-provided credentials, while remote HTTP access requires standards-based authorization, audience validation, least privilege, HTTPS outside localhost, and no token passthrough.

The authenticated website was also checked read-only. The observation found:

- an active Pro account;
- Chat and Work entry points;
- GPT-5.6 Sol selected, other current/legacy model choices, reasoning through Extra High and Pro, and Voice/Dictate controls;
- 22 records in the general account model catalog and four account-visible Work models;
- both older live Plugin envelopes and newer public-bundle Plugin variants;
- valid empty automation and Site list envelopes, with Sites access enabled.

The check opened no chat, sent no prompt, changed no model or setting, and started no Voice or Work session. Account content, identity, cookies, bearer tokens, raw payloads, and private signed URLs were not retained.

## 6. GPT-Live decision

GPT-Live cannot be exported today as a supported direct consumer-account MCP audio capability.

The reasons are independent:

1. The official Voice product page says Live does not initially support connected apps or plugins, Work, Codex, custom GPTs, Temporary Chats, or the desktop app.
2. MCP tools/resources are request-response contracts, not a full-duplex, low-latency browser audio transport.
3. The observed browser path is private WebRTC behavior, not a published consumer-account integration contract.
4. A transcript appearing after the session does not prove a safe live audio bridge or even the adapter's current transcript item shape.

A future experiment may use an optional local TypeScript/browser WebRTC sidecar controlled by the Python MCP server. It remains a separate safety/performance design and cannot be described as officially supported. It must not use the OpenAI API because the project requirement is consumer-account-only.

## 7. Language and performance decision

- **Python remains the MCP control plane.** This repository is network-, backend-, and streaming-latency dominated, and Python preserves the mature authenticated transport and smallest safe diff.
- **TypeScript is reserved for a future browser-native WebRTC sidecar.** Browser media APIs and WebRTC are the one area where it has a structural advantage.
- **Rust is deferred.** It should be introduced only after a reproducible benchmark identifies a CPU, memory, or transport bottleneck that Python and the current dependency architecture cannot resolve.

## 8. CI/CD and continuous compatibility

The design uses four separate gates:

1. **PR offline gate:** Ruff, supported Python/OS matrix, release metadata, ShellCheck, wheel/sdist build, `twine check`, clean installs, packaged Skill/resource checks, and sdist tests.
2. **Public no-secret radar:** scheduled/manual official-page and public-bundle fingerprinting; it never accesses a ChatGPT account or mutates source.
3. **Local exact-commit account gate:** maintainer-controlled, GET-only, shape-only, redacted, and outside hosted CI. Any source or package change invalidates its receipt.
4. **Post-merge release gate:** rebuild/test the exact merged commit before tagging, publish through the existing OIDC workflow, compare PyPI only with `release_workflow_artifacts`, attach and verify the pre-tag receipt, then clean-install from PyPI.

This is how the project can track fast ChatGPT changes without pretending that a scheduled public check validates private consumer-account routes.

## 9. Official MCP and Skill guidance applied

The current official Codex guidance favors:

- `AGENTS.md` for durable repository conventions;
- project configuration for repository-specific settings and personal configuration for user defaults;
- MCP when external context changes frequently or a repeatable live integration is needed;
- starting with one or two tools that remove a real manual loop, not exposing everything indiscriminately;
- Skills for repeatable methods, with a precise description and progressive disclosure;
- Plugins to distribute mature Skills and connectors;
- scheduled tasks only after a workflow is stable: the Skill defines the method, the task defines the schedule.

For gpt2agent this means one bounded read tool per coherent account job, explicit schemas and annotations, no opaque raw payload tool, a bundled Skill kept in sync with the server, stdio by default, and loopback-only HTTP until real transport authentication exists.

## 10. Parent-workspace hygiene audit

The actual Git repository is `/home/robot/workspace/47-chatgpt2agent/gpt2agent`. The parent `/home/robot/workspace/47-chatgpt2agent` is not a Git worktree.

Strict `AUDIT-*.md` matching returned zero files. Two likely intended files use underscores. The seven primary hygiene files total 1,981,636 bytes:

| Parent-workspace file | Size | Classification | Proposed disposition after owner approval |
| --- | ---: | --- | --- |
| `cx-fix.log` | 1,287,331 B | merged work; sensitive historical session log | delete |
| `cx-simplify.log` | 341,893 B | superseded v1 review | delete with v1 summary |
| `cx-simplify2.log` | 325,051 B | stale snapshot with some residual backlog | extract verified backlog, then delete |
| `SIMPLIFY-REPORT.md` | 4,093 B | superseded v1 summary | delete |
| `SIMPLIFY-PLAN-v2.md` | 3,622 B | partially useful but stale | refresh backlog into tracked plan/issue, then delete |
| `AUDIT_2026-05-15.md` | 7,673 B | historical audit referenced by a commit | privately archive or extract residuals, then delete |
| `AUDIT_2026-06-18.md` | 11,973 B | completed audit source-of-truth | archive/delete with its GOAL/VERIFY bundle |

Five associated files belong to the same cleanup decision: three `cx-*-prompt.txt` files, `GOAL_audit-remediation.md`, and `VERIFY_audit-remediation_2026-06-18.md`. All 12 candidates total 1,994,979 bytes.

None is tracked by either checked repository, present in Git object history, open according to `lsof`, or needed by an active worktree. All have mode `0664`. The three logs contain session/conversation identifiers, although a bounded scan found no token-like secret, bearer value, cookie, email, or API key. They should not remain world/group-readable or be moved into the public repository.

No file was deleted, moved, or chmodded because the request authorized inspection, not destruction of files created by other sessions. If retained temporarily, changing the three logs to `0600` is the minimum risk reduction, but that is also a mutation requiring owner approval under the workspace agreement.

## 11. Remaining gate

The design and cross-model review are ready for user re-approval. Code, dependency, CI, version, PR, tag, PyPI, and release changes must not begin until that approval because the corrected design materially defines feature scope and safety boundaries.
