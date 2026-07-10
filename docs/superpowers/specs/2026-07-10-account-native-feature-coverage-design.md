# Account-native feature coverage and compatibility design

- **Status:** Conversation-approved design, pending committed-spec review
- **Date:** 2026-07-10
- **Target release:** gpt2agent 0.0.12
- **Primary constraint:** Use the signed-in consumer ChatGPT account session only. Do not use an OpenAI API key, the OpenAI API, Realtime API billing, or a second service credential.

## 1. Context

gpt2agent is a local MCP server that uses the authenticated `chatgpt.com` account session. Its current Python implementation exposes 25 tools and passes the offline test suite, but its account-feature coverage and compatibility controls lag the current ChatGPT product:

- The account currently exposes Work models, Plugins, Sites, scheduled automations, voices, and newer reasoning-effort metadata that have no dedicated MCP surface.
- `list_apps` drops every string-valued app ID returned by the current `/backend-api/apps/list` response.
- `list_tasks` describes generic asynchronous account jobs as scheduled tasks even though scheduled automations live under `/backend-api/automations`.
- Browser client headers are fixed to a hard-coded build and client version, which creates an avoidable drift hotspot.
- The Python package allows any future MCP major version through `mcp>=1.26.0`, even though the official Python SDK documents v1 as the current stable line and v2 as pre-release work.
- ChatGPT changes faster than a manual release cycle, so release-time snapshots alone cannot reveal drift early.

This design adds reliable, read-only account coverage first, makes MCP and Skill contracts explicit, and creates a no-secret compatibility radar. It deliberately does not promise that undocumented ChatGPT web contracts are official or permanently stable.

## 2. Evidence and support boundary

Three evidence classes must remain distinct in code, documentation, and status output:

1. **Official product behavior.** OpenAI's current product documentation and release notes describe user-visible features and constraints.
2. **Public web-client contract evidence.** The deployed ChatGPT JavaScript bundle shows route names, query fields, and response fields consumed by the current website. This is useful compatibility evidence, not a supported API contract.
3. **Live account evidence.** A read-only check against the user's signed-in account proves entitlement and current reachability for that account at a timestamp. It does not make a private route official.

Every feature-coverage record therefore carries separate fields for:

- `entitled`
- `reachable_now`
- `exposed_by_mcp`
- `officially_supported`
- `evidence_source`
- `observed_at`

The first four fields must never be collapsed into one `supported` boolean. Unknown is represented as `null`, not guessed as `false`.

`officially_supported` describes the exact integration path from a consumer ChatGPT session into gpt2agent, not merely whether OpenAI documents the product feature. A feature such as Voice can be an official ChatGPT product while the private web route used by this project remains unsupported. The evidence reason must make that distinction explicit.

The official sources used for this design are:

- [ChatGPT release notes](https://help.openai.com/en/articles/6825453-chatgpt-release-notes)
- [ChatGPT What's new](https://learn.chatgpt.com/docs/whats-new)
- [Codex changelog](https://learn.chatgpt.com/docs/changelog)
- [Work in ChatGPT](https://help.openai.com/en/articles/20001275)
- [Sites in ChatGPT](https://help.openai.com/en/articles/20001339)
- [Plugins in ChatGPT and Codex](https://help.openai.com/en/articles/20001256-plugins-in-chatgpt-and-codex)
- [Voice in ChatGPT](https://help.openai.com/en/articles/20001274)
- [Build Skills for ChatGPT and Codex](https://learn.chatgpt.com/docs/build-skills)
- [Define tools](https://developers.openai.com/apps-sdk/plan/tools)
- [MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [MCP resources specification](https://modelcontextprotocol.io/specification/2025-11-25/server/resources)
- [MCP transports specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [MCP authorization specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [MCP security best practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices)
- [Agent Skills specification](https://agentskills.io/specification)
- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

### 2.1 Current evidence snapshot

The 2026-07-10 read-only audit established the following non-secret baseline:

- The authenticated website showed an active Pro account, Chat and Work entry points, GPT-5.6 Sol selected, GPT-5.5/GPT-5.4/GPT-5.3/o3 choices, reasoning choices through Extra High and Pro, and Voice/Dictate controls. The audit opened no chat, sent no prompt, changed no setting/model, and started no Voice or Work session.
- The account model catalog returned 22 models, including GPT-5.6 reasoning metadata; the Work catalog returned four account-visible models.
- The apps route returned 74 string IDs, which proves the existing object-only `list_apps` parser is lossy.
- The account exposed both older Plugin response variants (`list` and `results/page`) while the current public web bundle consumes newer `plugins/release` variants. The adapter must therefore recognize both without dumping raw unknown fields.
- The automations and Sites list routes returned valid empty `{items, cursor}` envelopes; Sites access was enabled. Empty is account state, not a route failure.
- The voice settings route returned nine account-visible voice IDs. Runtime names are authoritative for the catalog tool because rollout metadata can differ from help-page names.
- The project-list route returned HTTP 405, so project coverage is explicitly deferred.

The official update review covered the July 8–9 changes that motivate this release: GPT-Live-1/mini, GPT-5.6 and Work surfaces, Sites public beta, the Plugin Directory naming change, unified desktop Chat/Work/Codex entry points, and the corresponding Codex desktop/CLI changelog. These observations are a dated snapshot, not a perpetual compatibility claim.

### 2.2 Coverage decision matrix

| Account feature | Product evidence | Account/web route evidence | 0.0.12 MCP decision |
| --- | --- | --- | --- |
| General ChatGPT models and reasoning | Official product and release notes | `/backend-api/models` and conversation serializer | Keep `list_models`/`chat`; add live-validated `thinking_effort` |
| Work models | Official Work documentation | `/backend-api/tpp/models/` | Add `list_work_models` |
| Apps/connectors | Official connected-app product surface | `/backend-api/apps/list` | Fix mixed-entry `list_apps` normalization |
| Plugins | Official Plugin Directory documentation | `/backend-api/plugins/list` and `/installed`, with two observed schema generations | Add catalog and installed-plugin read tools with variant adapters |
| Generic asynchronous jobs | Product behavior; not scheduled-task proof | `/backend-api/tasks` | Keep `list_tasks`, correct its description |
| Scheduled automations | Official ChatGPT product surface | `/backend-api/automations` | Add a distinct scheduled-task read tool |
| Sites | Official Sites public-beta documentation | `/backend-api/websites` and `/access` | Add access and list tools; no creation/publication |
| Voice catalog and transcript | Official Voice documentation | `/backend-api/settings/voices`; transcript adapter path not yet proven | Add voice catalog; mark post-session transcript retrieval best-effort/unverified |
| GPT-Live audio | Official Voice product, with explicit initial feature exclusions | Private browser WebRTC evidence only | No stable audio export; defer an optional experimental sidecar |
| Projects | Official product feature | Candidate list route returned HTTP 405 | Explicitly unsupported in 0.0.12 |
| Existing conversations, GPTs, memory, instructions, Codex, images, tools, and research | Existing project coverage | Existing tested adapters/SSE paths | Retain and include in the feature-coverage resource; no unrelated expansion |

The packaged feature-coverage resource must inventory every existing MCP tool plus each known account feature in this matrix. A feature that is absent, unsafe, or deferred remains visible with a reason instead of disappearing from the inventory.

## 3. Goals

The 0.0.12 release will:

1. Fix incorrect normalization and naming in existing read tools without breaking their return shapes.
2. Add focused, read-only tools for scheduled automations, Plugins, Work models, Sites, voices, and account capabilities.
3. Add optional model-aware `thinking_effort` to `chat`.
4. Add MCP resources for release-time feature coverage and update evidence.
5. Apply explicit schemas, tool annotations, pagination, bounded inputs, redaction, and typed errors to new surfaces.
6. Tighten the existing MCP dependency to the stable v1 line without adding another runtime package.
7. Add package/release dry-run coverage to pull requests and a scheduled public, no-secret compatibility radar.
8. Preserve the existing local-account privacy boundary and prove a complete PR-to-release workflow for 0.0.12.
9. Close two existing account-exposure escape hatches: unauthenticated non-loopback HTTP and unredacted raw SSE dumps.

## 4. Non-goals

The 0.0.12 release will not:

- expose GPT-Live audio as a stable MCP tool;
- call the OpenAI Realtime API or require an API key;
- add a browser automation fallback;
- add account writes, plugin installation, Site publication, automation mutation, microphone capture, or destructive tools;
- claim a reliable project-list API while the live route returns HTTP 405;
- copy raw account responses into CI fixtures, logs, artifacts, or documentation;
- auto-edit code or auto-publish a release in response to compatibility-radar findings;
- add Rust or a TypeScript runtime sidecar in this release.

## 5. Language and performance decision

The MCP core remains Python for 0.0.12. Network latency, server processing, and streaming dominate this workload; replacing the mature client with Rust would add packaging and maintenance cost without addressing the main latency path. Python also preserves the existing tested transport, authentication, and redaction code with the smallest safe diff.

If an experimental GPT-Live bridge is pursued later, it should use a small optional TypeScript/browser sidecar for the browser-native WebRTC and media APIs while Python remains the MCP control plane. Rust is reserved for a measured CPU, memory, or transport bottleneck that cannot be resolved in the current architecture. No sidecar is shipped until benchmarks and a separate safety design justify it.

Performance rules for the Python path are:

- reuse the existing authenticated HTTP client and connection pool;
- avoid a browser launch or manifest fetch on every tool call;
- fetch independent account capability endpoints concurrently with a small concurrency cap;
- use bounded pagination and return cursors instead of collecting an unbounded account history;
- cache only non-content model/build metadata in memory for a short process-local lifetime;
- refresh model metadata once after a validation mismatch before returning an error;
- never persist conversations, prompts, transcripts, cookies, bearer tokens, or raw account payloads.

## 6. Architecture

```text
MCP client
   |
   | stdio by default
   v
Python FastMCP server
   |-- focused read tools
   |-- release-time evidence resources
   |-- schema validation / redaction / typed errors
   |
   v
BackendClient + ConversationClient
   |-- signed-in consumer ChatGPT session
   |-- bounded process-local metadata cache
   v
private chatgpt.com web routes and SSE conversation transport

Optional future lane, not in 0.0.12:
Python MCP control plane <-> local TypeScript WebRTC sidecar <-> GPT-Live web session
```

The server continues to prefer local stdio. Stdout is reserved for MCP protocol frames and logs go to stderr. For 0.0.12, HTTP is strictly loopback-only: the `GPT2AGENT_ALLOW_REMOTE` bypass is removed and every non-loopback bind is refused. Local HTTP also validates any supplied `Origin` against the configured loopback origin/port to prevent DNS rebinding; clients that do not send a browser `Origin` remain supported. Remote serving is deferred until the server has transport authentication; a warning plus a firewall recommendation is not an adequate control for a full-account proxy.

A future remote deployment must use Streamable HTTP, validate `Origin`, bind safely, and add OAuth 2.1/PKCE with audience validation; account tokens must never be passed through from an MCP client.

The backend adds a dependency-free process-wide concurrency limiter and conservative per-route invocation limits. Limits are configurable only within safe documented bounds, do not expose account state, and fail with retry guidance instead of queuing without bound. A 429 response activates route cooldown from a safe `Retry-After` value when present; it is never blindly retried in a tight loop.

## 7. MCP surface

### 7.1 Existing tools changed compatibly

#### `list_apps()`

Keep the existing list return shape. Normalize each entry from `/backend-api/apps/list` as follows:

- string: `{"id": value, "type": classify(value), "enabled": null, "connected": null}`
- object with a string `id`: preserve the current normalized fields
- `null`, non-string scalar, or object without a usable ID: skip

Ordering follows the backend response and duplicate IDs are not silently invented or renamed. Classification remains informational and may be `unknown`.

#### `list_tasks(limit=20)`

Keep the existing return shape and route for backward compatibility. Change its public description to “background/asynchronous ChatGPT jobs” and remove the scheduled-task claim from documentation. Validate `limit` within a documented bounded range.

#### `chat(prompt, model, temporary, thinking_effort=None)`

Add optional `thinking_effort`. When unset, omit `thinking_effort` from the serialized conversation body. When set:

1. Read the selected model's live `thinking_efforts`, `default_thinking_effort`, and `configurable_thinking_effort` metadata.
2. Accept only a value present in `thinking_efforts[].thinking_effort` for that model.
3. If the cached model metadata rejects it, refresh once and revalidate.
4. Return an `unsupported` tool error if the model does not expose configurable effort, and an invalid-input tool error when the value is outside the live allowed set.

Do not hard-code all UI renderer literals as valid for every model. The observed web serializer sends the snake-case scalar `thinking_effort` and omits it when unset.

### 7.2 New read-only tools

Each tool has one job, a bounded input schema, a structured output schema, and MCP annotations with `readOnlyHint: true`, `destructiveHint: false`, `idempotentHint: true`, and an accurate `openWorldHint`. New paginated list tools return `{"items": [...], "cursor": string|null}`.

#### `list_scheduled_tasks(cursor=None)`

- Route: `GET /backend-api/automations`
- Query: always send the observed `filter=scheduled`; add `cursor` only when provided. The web contract exposes no page-size input, so this tool does not invent one.
- Envelope: `items`, `cursor`
- Normalize only observed stable fields: `id`, `updated_at`, `next_run_times`, `is_enabled`, `target_time_utc`.
- Require only a usable item ID. `next_run_times`, `is_enabled`, and `target_time_utc` are nullable because paused/finished schemas have not been observed live; if `next_run_times` is present and non-null, validate that it is an array.

The current web client also uses `paused` and `finished`. Those filters and a broader all-automations tool are deferred until live non-empty samples can establish honest normalized contracts.

#### `list_plugins(scope="USER", limit=50, cursor=None)`

- Route: `GET /backend-api/plugins/list`
- Query: `scope`, bounded `limit`, and `pageToken` only when `cursor` is present.
- Valid observed scopes: `USER`, `WORKSPACE`.
- Preferred current-web envelope: `plugins`, `pagination.next_page_token`; current-web items require `id` and `release`.
- Also accept the live-account catalog envelope `list`, whose observed items expose `id`, `name`, `marketplace_name`, `version`, and `enabled` without a nested release.
- Return only this allowlisted scalar projection: `id`, redacted `name`, redacted `marketplace_name`, redacted `display_name`, `version`, `enabled`, `scope`, `status`, `installation_policy`, `release_version`, `skill_names`, `disabled_skill_names`, `app_ids`, `app_template_ids`, `canonical_connector_ids`, `mcp_server_keys`, and string-valued `capability_names`. Missing fields remain `null`; values are never fabricated across variants.
- Do not return release descriptions, prompts/default prompts, skill descriptions/interfaces, template descriptions/reasons, icons, screenshots, developer URLs, owner IDs, workspace IDs, or unknown nested objects.
- Bound `limit` to 1–50, cursors to 2,048 printable characters, names/IDs/versions/status scalars to 256 characters, and every projected nested string list to 100 entries. Apply secret/PII redaction to strings, drop non-string list entries, and return `contract_changed` when required identity fields or envelope types are invalid.
- If the legacy `list` envelope exceeds the requested limit without a usable continuation token, return `contract_changed` rather than silently truncate an unpageable catalog.
- Do not return owner account IDs or workspace IDs unless a documented use case and redaction review is added.

#### `list_installed_plugins()`

- Route: `GET /backend-api/plugins/installed`
- Send no pagination query.
- Accept the current-web `plugins` envelope and the live-account `results` plus `page` envelope. Return `{"items": [...]}`; the first-release tool does not claim pagination because the current web client sends an empty query and supplies no continuation request.
- Use the same exact allowlist and bounds as `list_plugins`; the live-account variant may derive only scalar IDs/names from `marketplace`, `apps`, and `skills` without returning those objects.
- Populate `enabled` and `disabled_skill_names` when supplied by the installation record.
- If the legacy `page` reports `has_more: true`, return `contract_changed`; no continuation query is supported by the observed installed-plugin contract.
- A response with neither a `plugins` nor a `results` list is `contract_changed`, not an empty list.

#### `list_work_models()`

- Route: `GET /backend-api/tpp/models/`
- Return a list of account-visible Work model records with slug/identifier, title, token limit, reasoning configuration, and observed default effort where present.
- Do not infer general chat-model availability from this Work-only catalog.

#### `sites_access()`

- Route: `GET /backend-api/websites/access`
- Return the normalized entitlement/access flags without account identifiers.

#### `list_sites(limit=20, cursor=None)`

- Route: `GET /backend-api/websites`
- Query: bounded `limit`; use `after=cursor` for subsequent pages.
- Envelope: `items`, `cursor`.
- Normalize observed fields: `id`, redacted `title`, redacted `slug`, `status`, `updated_at`, `disabled_by`, and `sharing` with `access_mode`, `user_count`, and `group_count`.
- Do not return `live_url`, `preview_url`, or `screenshot_url` in 0.0.12 because the empty live account sample cannot prove which URL shapes are public. Expose only `has_live_url`, `has_preview`, and `has_screenshot` booleans.
- A future public-URL field requires redacted non-empty evidence, a proven published/public status, an allowlisted URL-shape contract, and separate security review. No Site content is fetched.

#### `list_voices()`

- Route: `GET /backend-api/settings/voices`
- Return live voice IDs and display metadata supplied by the account response.
- Do not hard-code documentation names because voice catalogs can be rollout-specific.
- This is catalog access only; it does not claim audio streaming or speech synthesis.

#### `account_capabilities()`

- Query the fixed probe table below concurrently with a small cap. Adding, removing, or changing a probe is a reviewed contract change, not an adapter guess.
- Return `{"schema_version": "1", "observed_at": <UTC ISO-8601>, "capabilities": [...]}`. Every record has `id`, `entitled`, `reachable_now`, `exposed_by_mcp`, `officially_supported`, `evidence_source` (a bounded list of `official_doc`, `public_bundle`, `live_account`, or `packaged_contract`), `observed_at`, `status`, and a non-sensitive `reason`.
- Partial failure does not erase successful evidence. Failed lanes receive a typed status and `reachable_now: null` unless the response proves `false`.
- Do not include email, account IDs, raw flags, cookies, request headers, prompts, conversation titles, or content.

Normative probe table:

| Capability IDs | GET probe | Entitlement rule |
| --- | --- | --- |
| `chat_models`, `agent_mode`, `code_interpreter`, `canvas`, `image_generation`, `deep_research` | `/backend-api/models?history_and_training_disabled=false` | `true` only when the valid catalog explicitly advertises the model/tool/capability; otherwise `null` |
| `work_models` | `/backend-api/tpp/models/` | `true` for a valid non-empty account catalog; `null` for a valid empty catalog |
| `apps` | `/backend-api/apps/list` | `true` for a valid non-empty account catalog; `null` for a valid empty catalog |
| `plugins` | `/backend-api/plugins/list?scope=USER&limit=1` | `true` when a valid catalog item or explicit access field exists; `null` for a valid empty catalog |
| `installed_plugins` | `/backend-api/plugins/installed` | inherit proven Plugin entitlement; an empty valid installed list does not mean `false` |
| `background_jobs` | `/backend-api/tasks?limit=1` | `true` for a valid non-empty account result; `null` for a valid empty result |
| `scheduled_automations` | `/backend-api/automations?filter=scheduled` | use only an explicit account feature/access boolean; otherwise `null`, including a valid empty result |
| `sites` | `/backend-api/websites/access`, then `/backend-api/websites?limit=1` when access is true/unknown | use only the explicit boolean access result; never infer `false` from an empty Site list |
| `voice_catalog` | `/backend-api/settings/voices` | `true` for a valid non-empty catalog; `null` for a valid empty catalog |
| `conversations` | `/backend-api/conversations?offset=0&limit=1&order=updated` | `true` for a valid envelope, even when empty |
| `custom_gpts` | `/backend-api/gizmos/snorlax/sidebar` | `true` for a valid non-empty result; `null` when empty |
| `memory` | `/backend-api/memories` | `true` only from an explicit feature flag or non-empty valid result; otherwise `null` |
| `custom_instructions` | `/backend-api/user_system_messages` | `true` for a valid contract response; otherwise follow the truth table below |
| `codex` | `/backend-api/codex/environments` | `true` for a valid non-empty result; `null` when empty |
| `projects` | `/backend-api/projects` | no entitlement inference; a 404/405 proves only that this unestablished candidate route is `unsupported`, not that Projects are unavailable |
| `voice_transcript`, `gpt_live` | no content/session probe | `null`; a GET-only capability audit must not start Voice or read a conversation body |

Truth table applied independently to every probe:

| Probe outcome | `reachable_now` | `entitled` | `status` |
| --- | --- | --- | --- |
| Valid 2xx minimum schema | `true` | capability-specific rule above | `ok` |
| Explicit access boolean `false` in a valid response | `true` | `false` | `unavailable` |
| 401 | `null` | `null` | `login_required` |
| 403 without a safe explicit entitlement or retry code | `null` | `null` | `access_indeterminate` |
| 404/405 on an established adapter route | `false` | `null` | `contract_changed` |
| 404/405 on an unestablished candidate route such as Projects | `null` | `null` | `unsupported` |
| 422 caused by the packaged probe | `null` | `null` | `contract_changed` |
| Timeout, 429, or retryable 5xx | `null` | `null` | `temporarily_failed` |
| 2xx with malformed minimum schema | `null` | `null` | `contract_changed` |
| No permitted probe | `null` | `null` | `unverified` |

`exposed_by_mcp` comes only from the packaged server registry for this release. `officially_supported` is `false` for every private consumer-account route in this table, even when OpenAI officially documents the product feature. It may become `true` only if OpenAI publishes a supported contract for this exact integration path. A static product-documentation claim is listed in `evidence_source` and `reason`; it never overrides a live truth value.

### 7.3 MCP resources

Tools are used for live parameterized account queries. Resources are used for readable, non-secret release context:

- `chatgpt://feature-coverage` — the packaged 0.0.12 coverage matrix, its evidence classes, known limitations, and the release observation date.
- `chatgpt://update-evidence` — the packaged list of official release-note sources, checked timestamps, compatibility assumptions, and last public-radar result available at build time.

Both resources use `application/json` and a deterministic versioned schema. `update-evidence` contains the checked-in release snapshot, not a mutable GitHub Actions artifact. They contain no live account content. Large generated files are exposed by resource link or file reference rather than embedded as base64 tool output.

### 7.4 Errors and compatibility status

Correctable validation and backend failures are tool-execution errors, not MCP protocol errors. New adapters use these machine-readable codes:

- `unavailable` — a documented capability is not enabled or reachable for this account.
- `unsupported` — the requested operation or option is not supported by the selected feature/model.
- `contract_changed` — the private response no longer satisfies the adapter's minimum schema.
- `temporarily_failed` — retryable network, timeout, or upstream service failure.
- `access_indeterminate` — access was denied but the safe response evidence cannot distinguish entitlement, WAF, or session policy; this is not automatically retryable.
- `invalid_input` — local bounded-input or enum validation failed.
- `login_required` — the consumer ChatGPT session must be refreshed.
- `unverified` — no permitted non-mutating probe has established the capability path; this is a status, not a failure claim.

The implementation introduces a shared `BackendHTTPError` carrying only safe structured fields: HTTP method, normalized route name, status code, retryability, and sanitized retry delay. Response bodies, headers, request credentials, full URLs, and account identifiers are not attached. A separate `BackendContractError` carries the adapter name and failed invariant. The MCP boundary translates those exceptions into the codes above; adapters no longer parse strings from generic `RuntimeError` messages.

HTTP interpretation is conservative:

- 401 -> `login_required`
- 403 -> `access_indeterminate` with `retryable: false` by default because entitlement denial, WAF challenge, and session blocking cannot be distinguished from status alone; use `unavailable` only when an explicit entitlement field/safe code proves it, or `temporarily_failed` only when a safe retry code/`Retry-After` proves retryability
- 404 or 405 on an established adapter route -> `contract_changed`; on an unestablished candidate route -> `unsupported`; an optional capability probe may use `unavailable` only when independent entitlement evidence supports it
- 422 -> `invalid_input` when caused by caller input; `contract_changed` when a fixed packaged probe is rejected
- timeout, 429, and retryable 5xx -> `temporarily_failed`

Errors expose an action-oriented message and safe retry guidance. They never expose response bodies, tokens, cookies, headers, session/device IDs, or raw internal exceptions.

## 8. Official MCP and Skill practices

The implementation will apply these rules consistently:

- Use one job per tool and separate reads from writes.
- Use explicit JSON input and output schemas. Return `structuredContent` and a serialized JSON text fallback where client compatibility requires both.
- Bound list sizes and make pagination explicit.
- Annotate tools accurately; annotations describe risk but never replace authorization or server-side checks.
- Use tools for actions and parameterized queries, resources for readable context, and Skills for multi-step workflows.
- Keep Skill trigger descriptions precise enough that a client can select them without reading the body.
- Keep Skill instructions focused and progressively disclose the packaged tool reference. Prefer instructions over scripts; scripts must be deterministic when needed.
- Test Skill metadata, trigger examples/non-examples, package inclusion, reference links, and a practical size budget for `SKILL.md`.
- Keep the stable MCP major pinned as `mcp>=1.27,<2` for this release. Upgrading to v2 requires a separate compatibility change after it is stable and tested.

The bundled gpt2agent Skill and tool reference will be updated in the same feature PR so installed guidance cannot lag the server surface.

## 9. Safety and privacy

All newly added account-discovery tools are GET-only and need no confirmation. The optional `thinking_effort` parameter affects the already user-invoked `chat` generation path and does not create a separate background action. Existing write-capable tools receive an annotation and description audit, but their stable signatures do not change in this release.

Before adding any new account write, expensive generation, public/external action, or destructive action, the server must implement a short-lived, scoped, one-use confirmation token. A future Live bridge also requires an explicit microphone/audio-retention acknowledgement. The gate is not added as unused infrastructure in 0.0.12.

Privacy requirements:

- no personal ChatGPT token in GitHub Actions, repository secrets, fixtures, logs, or artifacts;
- expose only fields named by each tool contract; apply secret/PII redaction to returned free text and never return an opaque raw object;
- suppress private/signed URLs and strip userinfo, queries, and fragments from public URLs unless a separately reviewed tool requires them;
- never log raw private-route payloads;
- store no account-content cache;
- make shape-only local contract checks GET-only and opt-in;
- use synthesized fixtures that model only the minimum observed schema;
- never claim that consumer-account access is an official OpenAI API.

The existing `GPT2AGENT_RAW_DUMP` escape hatch violates this boundary because it persists prompts, responses, resume tokens, and raw SSE objects. Version 0.0.12 removes the raw-dump behavior and all documentation that recommends it. Setting the legacy variable fails closed with an actionable message. The changelog and migration note also explain that `GPT2AGENT_ALLOW_REMOTE` no longer bypasses loopback safety. If diagnostic files are reintroduced later, they require a separate allowlisted, shape-only schema; file mode `0600` alone is not sufficient protection.

## 10. GPT-Live decision

GPT-Live cannot be exported as a supported direct MCP capability today. The current official Voice documentation says Live does not initially support connected apps or plugins, Work, Codex, custom GPTs, temporary chats, or desktop. MCP is also a request/response tool and resource protocol, not a full-duplex low-latency audio transport.

Stable 0.0.12 coverage is limited to:

- the live account's voice catalog through `list_voices`;
- best-effort post-session transcript access through the existing conversation-history tools, subject to ChatGPT's transcript accuracy and retention behavior. This path remains `unverified` until an explicitly selected redacted conversation-body check proves the private adapter handles a Voice transcript shape.

A later experimental account-session bridge may use the private browser WebRTC routes observed in the signed-in web application. Its MCP surface would be control-only, such as `start`, `status`, `send_text`, `end`, and `get_transcript`; audio would remain on local WebRTC. It must be optional, disabled by default, labeled private/experimental, and isolated in a TypeScript sidecar so private media churn cannot destabilize the Python read server.

## 11. Browser-client metadata drift

Hard-coded `_CLIENT_VERSION` and `_CLIENT_BUILD` values are retained only as packaged fallback values. A small resolver will:

1. accept explicit validated environment overrides for diagnosis;
2. use a process-local last-known-good value when already resolved;
3. optionally inspect public ChatGPT bootstrap/manifest metadata at most once per process when a compatibility refresh is requested;
4. validate extracted values against strict length and character rules;
5. fall back safely to packaged values when public discovery fails.

The resolver extracts metadata only; it never downloads or executes arbitrary code, rewrites source, changes account settings, or persists account data. A failed request may trigger one metadata refresh and one retry only when the request is safe and idempotent.

## 12. Testing strategy

### 12.1 Adapter and unit tests

Use synthesized fixtures for:

- string, object, mixed, missing, and malformed app entries;
- empty and populated `{items, cursor}` automation/Site envelopes;
- Plugin list pagination and installed-plugin envelope differences;
- Work model and voice normalization;
- capability partial failures and truth-state separation;
- redaction of sensitive fields and safe URL handling;
- suppression of signed Site URLs and sanitization of `live_url`;
- each typed backend exception and MCP error mapping;
- refusal of every non-loopback HTTP bind, including the legacy override, plus loopback `Origin` validation;
- fail-closed handling of the legacy raw-dump variable;
- concurrency/rate limits, 429 cooldown, bounded retry, and safe `Retry-After` parsing;
- omission, acceptance, refresh, and rejection of `thinking_effort`;
- public metadata resolver overrides, validation, caching, retry bounds, and fallback;
- MCP resource schemas, URIs, and absence of account content;
- tool annotations and structured output schemas;
- Skill triggers, packaged references, and wheel/sdist inclusion.

Every adapter must distinguish an honestly empty collection from a malformed contract.

### 12.2 Local live contract tests

An explicit live test group is opt-in from normal `pytest` and is never run in hosted CI. It is nevertheless a required manual pre-release gate, run by the release owner with a maintainer-controlled local ChatGPT Pro session. A checked-in generator emits a schema-validated, canonically serialized receipt containing schema version, package version, full Git commit SHA, Git tree SHA, wheel/sdist filenames and SHA-256 values from the same checkout, plan class, UTC timestamp, adapter status, counts, and redacted shape results. It never records account identity or content. The receipt file's SHA-256 is computed externally and recorded in release evidence.

The live group must:

- issue GET requests only;
- validate envelope and minimum field shapes, not personal values;
- avoid reading conversation bodies unless a user explicitly selects that test;
- redact all diagnostic output;
- leave no snapshots, cookies, screenshots, or temporary account artifacts;
- report entitlement, reachability, and official support separately.

An honestly empty collection or explicitly proven unavailable entitlement passes the live route/envelope check. Populated item contracts are proven by synthesized fixtures derived from public-bundle field access and any separately approved redacted evidence; the release does not create a Site or automation merely to populate a test. Voice transcript parsing is not part of the required gate and remains marked unverified until a user explicitly selects an existing Voice conversation for a content-safe test.

The gate is invalidated by any subsequent source, test, dependency, build, or version change. It is run once on the final reviewed PR head and again on the merged `main` commit immediately before tagging. The pre-tag receipt becomes a GitHub Release asset; its local copy is deleted only after upload and digest verification.

### 12.3 Pull-request CI

The required PR pipeline continues to run Ruff, release-metadata verification, the offline test matrix on supported Python and OS versions, Windows package smoke tests, and ShellCheck. It additionally builds wheel and sdist, runs `twine check`, installs both artifacts in clean environments, checks packaged Skills/resources, and runs the narrow sdist tests. This is a release dry-run only: it never uploads to PyPI or creates a GitHub release.

The aggregate `required` job includes the package dry-run so branch protection has one reliable gate.

### 12.4 Scheduled public compatibility radar

A separate scheduled/manual workflow runs without account credentials or repository secrets beyond the default read token. It checks:

- official ChatGPT release notes, What's New, Voice, Work, Sites, and Plugins pages for a normalized content fingerprint;
- the official Codex changelog;
- the public ChatGPT manifest for route/query/envelope markers used by the adapters;
- the current stable MCP v1 release and latest MCP specification date;
- packaged fallback client/build metadata freshness.

The radar writes a redacted JSON/Markdown evidence artifact and GitHub Actions annotations. Contract-marker loss fails the radar visibly; documentation fingerprint changes produce a review-needed result. It does not open a PR, modify source, access a ChatGPT account, or release automatically. A maintainer reviews the evidence, performs an opt-in local account contract check where needed, then ships a normal tested PR.

## 13. Release and rollback workflow

Implementation starts in an isolated feature worktree after an implementation plan is approved. Changes are test-first and kept in reviewable commits. The release path is:

1. Implement adapters, resources, docs/Skill updates, tests, and CI radar.
2. Bump all coordinated version metadata to 0.0.12 and add a complete changelog/migration entry before release-candidate verification.
3. Run the full offline suite, Ruff, release verifier, package dry-run, secret scan, and `git diff --check`; commit the intended release candidate.
4. Run the required local GET-only contract group on that commit and generate the non-identifying receipt defined in section 12.2 from the same checkout/artifacts.
5. Open a PR, obtain independent review, resolve every thread, and require all CI gates green.
6. After the final PR revision, rerun step 3 and the live gate. The receipt must name the exact reviewed PR-head commit/tree and candidate artifact hashes. Any later revision invalidates it.
7. Merge to `main` without tagging. Check out the exact merged commit, verify it is on `origin/main`, rerun the package dry-run and live gate, and generate a new receipt naming the merged commit/tree and artifact hashes.
8. Create and push annotated `v0.0.12` only after step 7 passes. Include the pre-tag receipt SHA-256 in the annotated tag message.
9. Let the existing OIDC release workflow build and publish. Verify PyPI filenames and SHA-256 hashes match that workflow's built artifacts, the GitHub Release exists, and a clean install reports 0.0.12.
10. Attach the pre-tag receipt to the GitHub Release and verify its SHA-256 matches the tag annotation.
11. Remove only owned worktrees, build output, logs, receipts, and temporary artifacts after required uploads. Preserve and report any pre-existing unrelated worktree changes instead of forcing global cleanliness.

If publication fails after any artifact reaches PyPI, fix forward with the existing immutable version and workflow retry semantics where possible, or a new patch version when artifact contents must change. Never move or silently replace a published tag.

## 14. Acceptance and completion criteria

### 14.1 Pre-merge acceptance

The release candidate is ready to merge only when all of the following are true:

- mixed live app entries normalize correctly and no string IDs disappear;
- generic jobs and scheduled automations are represented by distinct tools and documentation;
- all new read tools satisfy their documented schemas on synthesized variants and the release owner has completed the required local shape-only gate on the exact final reviewed PR-head commit; honest empty/unavailable outcomes are recorded separately from populated fixture coverage;
- `thinking_effort` is omitted by default and validated against the selected live model when supplied;
- feature status preserves entitlement, reachability, MCP exposure, official support, evidence source, and observation time separately;
- the packaged coverage resource accounts for every existing MCP tool and every known feature in the dated decision matrix, including explicit deferred/unsupported entries;
- MCP resources resolve with deterministic non-secret content;
- new tools have explicit schemas, pagination, bounds, annotations, redaction, and typed errors;
- non-loopback HTTP is impossible, the unredacted raw-dump escape hatch is removed, and limiter/cooldown tests pass;
- bundled Skill guidance is updated and trigger/package tests pass;
- dependency metadata constrains the stable MCP v1 major;
- no CI job contains a consumer ChatGPT credential;
- the scheduled public radar reports evidence without mutating source or account state;
- the PR package dry-run installs and checks wheel and sdist cleanly;
- the complete offline test matrix, lint, release checks, and independent review pass;
- the candidate receipt records version 0.0.12, the final PR-head commit/tree, candidate wheel/sdist hashes, and redacted live results;
- no unexplained owned residue remains; the implementation worktree contains only the intended commits and any unrelated user changes are preserved and reported.

### 14.2 Pre-tag acceptance on merged `main`

The annotated tag may be created only when:

- the merged commit is verified on `origin/main` and contains the reviewed release-candidate tree;
- the package/release dry-run passes from that exact merged commit;
- the required local live gate passes from that exact merged commit;
- the pre-tag receipt records version 0.0.12, merged commit/tree, wheel/sdist hashes, and redacted live results;
- the annotated tag message records the receipt SHA-256.

### 14.3 Post-publish completion

The release is complete only after:

- the annotated `v0.0.12` tag is verified on the merged `origin/main` commit;
- PyPI exposes the expected wheel and sdist and every filename/SHA-256 matches the workflow artifacts;
- the GitHub Release exists with the correct changelog section;
- the attached pre-tag receipt matches the SHA-256 recorded in the annotated tag;
- a clean environment installs from PyPI and reports `gpt2agent 0.0.12`;
- all owned release artifacts and temporary worktrees are removed, while unrelated user changes are preserved and reported.

## 15. Deferred work

The following require separate designs and releases:

- an experimental GPT-Live WebRTC sidecar;
- confirmation-gated account writes and destructive/public actions;
- remote authenticated MCP hosting;
- project listing if a stable reachable account route emerges;
- paused/finished and broader all-automation filters, plus detailed item schemas, after safe non-empty evidence exists;
- adoption of MCP Python SDK v2 after a stable release and migration test matrix;
- any Rust component, contingent on a reproducible benchmark showing a meaningful bottleneck.
