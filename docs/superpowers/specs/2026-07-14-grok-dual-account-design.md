# Grok Dual-Account Backend and v0.0.13 Release Design

**Date:** 2026-07-14

**Status:** Approved design; implementation not started

**Target release:** `v0.0.13`, after `v0.0.12` is merged, tagged, and verified

**Supersedes:** `2026-07-11-grok-subscription-account-design.md` and its
constrained one-turn CLI-only product boundary

## 1. Objective

Add a Grok subscription account to gpt2agent in the same product sense that the
existing ChatGPT account is available: agents should be able to use both Grok
subscription surfaces available to the user.

1. The **Grok Build lane** uses the official Grok Build CLI and its CLI-owned
   OAuth state.
2. The **Grok website lane** uses the grok.com subscription conversation
   session and exposes the website conversation feature surface, including
   Auto, Fast, Expert, and Heavy multi-agent modes.

The two lanes have different credentials, endpoints, capabilities, quotas, and
failure modes. They must remain separately visible rather than being collapsed
into a single ambiguous token or readiness flag.

The delivered result includes a worktree, feature branch, reviewed pull request,
and a new `v0.0.13` release tag and package publication after `v0.0.12`.

## 2. Evidence Behind the Design

The design is based on current, non-secret evidence gathered on 2026-07-14.

- The official Grok Build CLI resolves to version `0.2.99` on this host and is
  authenticated through grok.com.
- The CLI auth file is mode `0600` and contains one JWT access credential plus a
  refresh token. Only schema and non-secret JWT claims were inspected; no token
  or identity value was printed or stored in the repository.
- The Build JWT carries `grok-cli:access`, `api:access`,
  `conversations:read`, and `conversations:write` scopes. Its audience is the
  CLI OAuth client.
- A read-only request to grok.com's website backend with only that Build bearer
  returned `403`, proving that scope names do not make the CLI bearer a website
  session credential.
- The logged-in Chrome profile has grok.com `sso` and `sso-rw` cookies. The live
  website uses cookie-authenticated requests with `credentials: include`.
- The live account returned the website modes Auto, Fast, Expert, and Heavy;
  Heavy is described in the UI as a “Team of Experts” and maps to
  `grok-4-heavy` / `MODEL_MODE_HEAVY`.
- The current website contract creates conversations with
  `POST /rest/app-chat/conversations/new`, supports model/mode discovery through
  `POST /rest/models` and `POST /rest/modes`, and exposes exact response-ID
  reconnect routes for asynchronous work.
- xAI's public documentation describes Grok Build as a distinct coding-agent
  product using `cli-chat-proxy.grok.com` and `auth.x.ai`. xAI also describes
  Heavy as parallel test-time compute with multiple agents.

The website endpoints are private implementation details and can drift. Runtime
contract validation, live gates, and explicit `GROK_WEB_CONTRACT_CHANGED`
failures are required; tests must not turn observed behavior into a claim of an
official public API.

## 3. Scope

### 3.1 Included in v0.0.13

- Independent Build and website auth/readiness reporting.
- Official-CLI Build agent calls with bounded process execution.
- Website Auto, Fast, Expert, and Heavy conversation modes.
- Web and X search controls and structured citations/search results.
- Private conversations by default, with explicit persistent history.
- Conversation creation, continuation, list, get, and delete.
- File upload through a separate, root-constrained tool and attachment IDs.
- Website response metadata, tool-use summaries, Heavy progress, and available
  multi-agent/trace metadata.
- Non-duplicating Heavy reconnect and result collection.
- Browser-assisted website-cookie import with a hidden manual fallback.
- Documentation, bundled skill guidance, release notes, version bump, tag,
  publication, and clean-install verification.

### 3.2 Deferred from v0.0.13

- Imagine image or video products.
- Voice and Grokcasts.
- Projects, workspaces, app deployment, and automations.
- Gmail, Outlook, Google Drive, calendar, SharePoint, or other external
  connectors.
- Website memory administration beyond an explicit per-chat `use_memory` flag.
- Subscription purchase, billing, team administration, or quota mutation.
- Emulating the website through the Build proxy.

“Website conversation parity” in this release means the conversation surface in
section 3.1. It does not mean every product linked from grok.com's sidebar.

## 4. Architecture

```text
MCP clients / coding agents
        |
        +-- Website tools
        |      grok_chat / grok_heavy / grok_heavy_result
        |      grok_upload_file
        |      grok_list_conversations / grok_get_conversation
        |      grok_delete_conversation
        |      grok_web_models / grok_web_status
        |              |
        |        GrokWebClient
        |        cookie reload + Chrome TLS impersonation
        |              |
        |        grok.com /rest/app-chat/*
        |
        +-- Build tools
               grok_build_agent
               grok_build_models / grok_build_status
                       |
                 GrokBuildClient
                 bounded official CLI subprocess
                       |
                 cli-chat-proxy.grok.com
```

### 4.1 Component boundaries

`GrokBuildClient` owns only official CLI resolution, child environment
construction, bounded process execution, output parsing, and exact session
operations. It does not parse or return the CLI credential.

`GrokWebAuthStore` owns only website-cookie loading, validation, mtime tracking,
and redacted source metadata. It has no HTTP behavior.

`GrokWebClient` owns website request construction, response parsing, contract
validation, retry classification, and conversation operations. It accepts an
auth-store interface and an injectable transport so tests never need real
cookies.

`GrokUploadPolicy` owns configured root resolution, symlink containment, size and
type bounds, and upload metadata validation. Chat accepts only previously issued
attachment IDs.

The MCP registration layer validates public inputs, calls one client method, and
returns stable dictionaries. It contains no token, HTTP, subprocess, or parser
logic.

## 5. Authentication

### 5.1 Build auth

- The official CLI remains the only reader and refresher of its OAuth state.
- gpt2agent selects the intended CLI profile with `GROK_HOME` and, when needed,
  `GROK_AUTH_PATH`.
- Ambient `XAI_API_KEY` is removed from child environments so subscription OAuth
  is not silently replaced with metered API-key usage.
- Build readiness comes from actual CLI version/model probes, not file presence.

### 5.2 Website auth import

`gpt2agent grok-setup` performs two independent probes: Build login and website
login.

For website login it prefers the installed `browser-use` CLI and an explicitly
selected Chrome profile. It imports only:

- `sso`
- `sso-rw`
- `grok_device_id`
- `cf_clearance`, when present and currently needed

It does not export the rest of the browser cookie jar, local storage, history,
passwords, bookmarks, or identity fields. Browser automation is closed after the
import.

If browser assistance is unavailable, hidden input accepts the minimum cookie
set. Secret input is never echoed.

The destination defaults to `~/.gpt2agent/grok-web-auth.json`. The file is
created or atomically replaced at mode `0600`. Parent directories are not made
group/world writable. The stored schema contains version, cookie name/domain/
path/expiry metadata, and secret cookie values. Documentation and fixtures use
placeholders only.

`gpt2agent grok-setup --refresh` repeats the import. Runtime watches the selected
file's mtime and reloads it between requests. Runtime does not silently launch or
control Chrome.

### 5.3 No cross-lane fallback

- A website `401` or `403` never retries with the Build JWT.
- A Build auth or quota failure never falls back to website cookies.
- No tool accepts a raw token/cookie argument.
- Status results never contain token values, cookie values, email, user ID,
  account ID, or refresh credentials.

## 6. Public Tool Contracts

### 6.1 `grok_chat`

Inputs:

- `prompt: str`
- `mode: Literal["auto", "fast", "expert"] = "auto"`
- `conversation_id: str | None = None`
- `temporary: bool = True`
- `search: Literal["off", "web", "web+x"] = "web+x"`
- `attachment_ids: list[str] = []`
- `use_memory: bool = False`

Heavy is rejected here with an actionable instruction to call `grok_heavy`.
`use_memory=True` requires `temporary=False`.

Result:

```json
{
  "surface": "web",
  "status": "complete",
  "conversation_id": "...",
  "response_id": "...",
  "model": "grok-4",
  "mode": "expert",
  "temporary": true,
  "text": "...",
  "citations": [],
  "search_results": [],
  "tool_results": [],
  "agents": [],
  "warning": null
}
```

Only stable, sanitized fields are returned. Unknown server fields are ignored
unless a required contract field is missing.

### 6.2 `grok_heavy`

Inputs are the Heavy-compatible subset of `grok_chat` plus
`wait_seconds: int = 600`. The tool forces the current live Heavy mode/model and
asynchronous response behavior.

It returns either `status="complete"` with the full stable result or
`status="in_progress"` with the exact `conversation_id`, `response_id`, observed
progress, and the instruction to call `grok_heavy_result`. A timeout is not
reported as completion and does not dispatch a second request.

### 6.3 `grok_heavy_result`

Inputs:

- `response_id: str`
- `wait_seconds: int = 600`

The tool reconnects only to that response. It cannot create a new Heavy request.
It returns the same complete/in-progress result contract as `grok_heavy`.

### 6.4 Website discovery and history

- `grok_web_models()` returns available model IDs, modes, tags, and defaults from
  the current account catalog. It does not report unavailable models as usable.
- `grok_web_status()` reports configured/authenticated/contract-ready state and
  capability booleans without identity.
- `grok_list_conversations(limit=20)` returns sanitized summaries.
- `grok_get_conversation(conversation_id)` returns the active message/response
  chain with citations and tool summaries.
- `grok_delete_conversation(conversation_id)` deletes exactly one conversation
  and returns a deletion receipt.

### 6.5 `grok_upload_file`

Inputs:

- `path: str`

The resolved file must be a regular file beneath a configured upload root. The
policy rejects symlink escapes, devices, sockets, oversized content, disallowed
types, and paths outside all roots. The result returns an attachment ID, sanitized
name/type/size, and no signed storage credential.

### 6.6 Build tools

`grok_build_agent` inputs:

- `prompt: str`
- `cwd: str | None`
- `mode: Literal["plan", "apply"] = "plan"`
- `model: str | None`
- `max_turns: int`
- `subagents: bool`

`cwd` must be beneath a configured Build root. `plan` is read-only by default.
`apply` is an explicit caller choice and maps to the CLI's documented permission
and sandbox controls. The tool returns session ID, result text, stop reason,
usage, and changed-file summary when available.

`grok_build_models` and `grok_build_status` report only the official CLI lane.

## 7. Website Data Flow

1. Validate prompt size, mode, persistence, search, attachment IDs, and memory
   combinations.
2. Reload website auth if the selected file's mtime changed.
3. Construct the current browser-compatible session with Chrome TLS
   impersonation, `Origin`, `Referer`, locale, and cookie jar. Never log request
   headers.
4. For new chat, POST the current `/rest/app-chat/conversations/new` shape with
   the explicit mode, model, temporary flag, search/tool controls, attachments,
   and memory controls.
5. For continuation, use the exact conversation/response route required by the
   current contract; do not create a second conversation.
6. Validate the response envelope before extracting conversation ID, response
   ID, answer text, citations, search results, tool results, trace steps, and
   agent metadata.
7. For Heavy, retain the exact IDs and reconnect with the response-ID route until
   complete, the caller's wait budget expires, or a terminal error occurs.
8. Return `in_progress` when the run remains active. Never infer completion from
   a quiet interval, partial text, or HTTP success alone.
9. Redact all error material before it crosses the client boundary.

## 8. Error Contract

Build codes:

- `GROK_BUILD_CLI_NOT_FOUND`
- `GROK_BUILD_AUTH_MISSING`
- `GROK_BUILD_QUOTA`
- `GROK_BUILD_TIMEOUT`
- `GROK_BUILD_OUTPUT_TOO_LARGE`
- `GROK_BUILD_FAILED`

Website codes:

- `GROK_WEB_AUTH_MISSING`
- `GROK_WEB_AUTH_EXPIRED`
- `GROK_WEB_RATE_LIMITED`
- `GROK_WEB_CONTRACT_CHANGED`
- `GROK_WEB_TIMEOUT`
- `GROK_WEB_OUTPUT_TOO_LARGE`
- `GROK_UPLOAD_BLOCKED`
- `GROK_WEB_FAILED`

Heavy `status="in_progress"` is a successful resumable receipt, not an error
code. Only a terminal failure raises one of the codes above.

Messages may include endpoint names, status codes, retry timing, configured path
labels, and stable error codes. They must not include JWTs, refresh tokens,
cookies, `Authorization`/`Cookie` headers, signed URLs, raw bodies, email/account
identity, complete environment dumps, or arbitrary CLI stderr.

## 9. Security Boundaries

- Website access uses a private, unsupported backend and must be documented as
  such. The official-CLI Build lane must not be described as making the entire
  Grok integration official.
- Both MCP transports remain local by default. The existing remote-bind guard
  applies to both account backends.
- Cookie storage is mode `0600`; setup writes are atomic and secret-safe.
- Debug capture is off by default and may never include credentials. A future raw
  traffic dump requires a separate explicit design because website bodies can
  contain private history and signed asset URLs.
- Upload roots default to disabled until configured. Each path is re-resolved at
  open time to reduce time-of-check/time-of-use and symlink risks.
- Build apply mode is explicit. Website deletion is an explicit separate tool.
- Ordinary and Heavy live tests use private conversations by default and clean up
  any server-side object the website still persists.
- Quota-bearing Heavy calls are never retried on ambiguous transport failure.

## 10. Testing and Verification

### 10.1 Unit tests

- Cookie schema, required names, expiry, permissions, atomic replacement, mtime
  reload, and secret redaction.
- Config validation, upload roots, symlink escapes, type/size limits, prompt and
  wait bounds.
- Exact website request shapes for new chat, continuation, search controls,
  attachments, private/persistent modes, and Heavy.
- Sanitized fixtures for ordinary responses, citations, search/tool results,
  multi-agent traces, partial Heavy responses, reconnect completion, quota,
  auth expiry, malformed JSON, HTML/Cloudflare responses, and contract drift.
- Build argv, subprocess bounds, permission mapping, profile selection, session
  handling, and process-tree cleanup.
- Tests proving no exception/result/log includes planted token, cookie, identity,
  header, signed URL, prompt, or raw backend detail.

### 10.2 Local integration tests

An injectable fake transport serves the observed website protocol locally. It
proves ordinary chat, continuation, history, attachment IDs, Heavy dispatch,
in-progress receipts, exact reconnect, and the invariant that result polling
cannot create a second paid request.

### 10.3 Opt-in live gates

Live tests are skipped in normal CI and require explicit flags.

1. Build CLI: account model discovery, exact sentinel, bounded completion, and
   owned-session receipt.
2. Website ordinary chat: private Auto/Expert sentinel plus one bounded search
   query that proves citation/search metadata.
3. Website Heavy: one minimal private Heavy request proving the live Heavy
   model/mode, observable multi-agent or trace evidence, exact response-ID
   reconnect, terminal completion, and no duplicate dispatch.

A live test that cannot observe multi-agent evidence is not sufficient to claim
Heavy parity, even if the final answer is correct.

### 10.4 Repository and package gates

- Full pytest suite with unrelated live tests skipped.
- Ruff and compileall.
- `git diff --check` and intended-file/diff audit.
- Wheel and sdist build plus Twine check.
- Clean-wheel installation, CLI help/setup smoke, imports, tool registration, and
  packaged docs/skills inspection.
- Independent code and security review.
- GitHub checks, review decision, mergeability, and release workflow inspection.

## 11. Worktree, PR, and Release Sequence

1. Preserve the current `feat/grok-account-cli` worktree until the replacement
   lane is safely created. Treat its CLI-only implementation as a prototype, not
   the release basis.
2. Create `.worktrees/gpt2agent-grok-dual-account` on
   `feat/grok-dual-account-v0.0.13`, based on PR #30's
   `release/v0.0.12-account-design` head.
3. Implement and verify on the stacked branch. Open its PR against the PR #30
   branch while #30 is pending so the review diff contains only v0.0.13 work.
4. After PR #30 merges, verify the published `v0.0.12`, update/retarget the
   feature PR to `main`, and reconcile only actual upstream conflicts.
5. Bump `0.0.12` to `0.0.13` and update release notes, docs, bundled skills, tool
   counts, and package metadata in the feature PR.
6. Require green checks, required review approval, and merge-ready state. Do not
   bypass repository governance.
7. Merge the verified PR, create annotated tag `v0.0.13` from the exact merge
   commit, and monitor the release workflow and PyPI publication.
8. Install `gpt2agent==0.0.13` into a fresh isolated environment and run
   non-destructive Build/web status probes.

## 12. Completion Criteria

The objective is complete only when current evidence proves all of the following.

- A dedicated worktree and `feat/grok-dual-account-v0.0.13` branch contain the
  intended dual-backend implementation.
- Build and website credentials are independently selected, refreshed/reloaded,
  redacted, and reported.
- Website Auto, Fast, Expert, and Heavy are discovered from the account and the
  approved tools implement conversation parity.
- Heavy live evidence proves the multi-agent/trace contract and non-duplicating
  reconnect behavior.
- Build plan/apply boundaries, upload roots, private defaults, auth storage, and
  redaction tests pass.
- Existing ChatGPT behavior and the full offline suite remain green.
- The PR is reviewed, green, merged, and based on verified `v0.0.12` state.
- Annotated `v0.0.13` points to the verified merge commit.
- The release workflow and PyPI publication succeed.
- A fresh install reports version `0.0.13`, exposes both Grok lanes, and passes
  non-destructive account-status checks.
- Final handoff lists exact commits, PR, tag, package URL, changed files,
  verification commands/results, live receipts, and any remaining website
  contract-drift risks.

## 13. References

- Grok Build overview: <https://docs.x.ai/build/overview>
- Grok Build CLI reference: <https://docs.x.ai/build/cli/reference>
- Grok Build headless scripting: <https://docs.x.ai/build/cli/headless-scripting>
- Grok Build enterprise authentication and network boundaries:
  <https://docs.x.ai/build/enterprise>
- xAI Grok 4 / Heavy announcement: <https://x.ai/news/grok-4>
- xAI Grok Build announcement: <https://x.ai/news/grok-build-cli>
