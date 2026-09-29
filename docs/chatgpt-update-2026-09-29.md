# ChatGPT compatibility update — September 29, 2026

This release updates the existing ChatGPT Chat integration. ChatGPT product
announcements do not automatically add endpoints or capabilities to this MCP
server. The account catalog, a completed request, and a supported product
surface are separate evidence.

## Models

OpenAI documents **GPT-6.1 Sol** (`gpt-6.1-sol`) for Codex and ChatGPT Work,
with access dependent on plan, client, workspace settings, and rollout.
Both checked Pro accounts expose `gpt-6.1-sol-wm` in
`GET /backend-api/models?history_and_training_disabled=false` (24 entries
per account). A live Chat request for each of `gpt-6.1-sol-wm` and `gpt-6.1-sol` on account A
resolved to `gpt-5-6`; both replies carried a *Model note*. These were two
completed routing checks, not successful GPT-6.1 executions.

The default remains `gpt-5-6`. `gpt-6-pro` is the heavier Chat model used by
this project's heavy-research lane; it is not the Codex ID `gpt-6-astra`.
`list_models` continues to return upstream catalog entries dynamically,
including newly added entries. Replies include a *Model note* when upstream
reports a resolved model different from the requested slug.

GPT-5.5 retires from ChatGPT, Work, and Codex on October 14, 2026; the API is
unaffected. Current defaults already avoid GPT-5.5. User configurations may
still need migration.

## Announcement coverage

| Announcement | Effect on this release |
| --- | --- |
| GPT-6.1 Sol | Document the Work/Codex boundary; expose the upstream catalog without hard-coded model lists. |
| Astra Ultrafast | No speed or billing promise for Chat backend requests; Work/Codex access does not configure this client. |
| Dots and Team Tasks | No new lifecycle or event-trigger APIs claimed. Existing `list_tasks` remains account introspection. |
| Work across devices | Existing Codex task/environment tools remain; they do not implement desktop session sync. |
| ChatGPT Space and Pages | No Space editing tools implemented or verified. Existing Canvas deprecation remains documented. |
| Reusable cloud environments and Security Cloud | Existing environment listing does not imply environment publication, security scanning, or patch execution support. |
| Sign in with ChatGPT for apps | This package still reuses local authentication as documented. It does not claim enrollment in the new partner sign-in program. |
| Plugin Extensions and MCP Events | Current server remains on supported `mcp>=1.27,<2`; event subscriptions require MCP 2.0. The separate MCP 2 migration PR is not folded into this maintenance release. |
| Slack/Teams and workspace connections | Existing app listing and connector hints remain; no new message-sending or administrator APIs added. |
| Website annotations | No browser annotation extension implemented. |

## Reliability updates

- Light research uses the configured Chat model after retirement of the
  legacy `research` request path. Its reader now handles current v1 delta
  envelopes, patches, continuations, and citation metadata.
- Heavy research checks model caps before posting and rejects detected
  downgrades or empty terminal output.
- Local rate-limit state is separated by `CODEX_HOME`; the new
  `gpt2agent ratelimit --json` command reads it without network access.
- Temporary conversation recovery stops on the first 404. A persistent
  retry requires explicit `temporary=False`; no privacy setting is changed
  and no replacement conversation is sent automatically.
- Release emulation uses unique build and environment directories, so
  parallel checks cannot overwrite another lane's artifacts.

## Verification boundaries

The v0.0.24 candidate integrates the source changes from PR #83 (light research recovery) and PR #86
(heavy research and account pacing). The compatibility and release receipts
live in `artifacts/verify/release-0.0.24/` and the release preparation report.
Doctor probes are read-only: an open conversation gate is not proof that
an image, agent task, or research report completed. Historical tool results
in the README retain their original dates.

A prepared branch and built wheel are not a published release. The proposed
tag is `v0.0.24`; owner approval is required before tagging or publication.

## Official sources checked

- [September 28–October 2 updates](https://learn.chatgpt.com/docs/whats-new)
- [GPT-6.1 Sol availability](https://learn.chatgpt.com/docs/models#gpt-61-sol)
- [GPT-6.1 Sol API model](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
