# Changelog

All notable changes to this project will be documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning: [SemVer](https://semver.org/).

## [0.0.3] - 2026-06-03

### Fixed

- **Light Deep Research report extraction.** The research model often emits a
  short tool-dispatch JSON as the FIRST `done` event (e.g.
  `{"queries":[...],"source_filter":[...]}`); the bundled runner took that first
  done as the report and silently discarded the real, later report. It now picks
  the longest `done` and falls back to all streamed progress text.

### Added

- **Multi-account auth via `CODEX_HOME`.** `BackendClient` reads
  `$CODEX_HOME/auth.json` (falling back to `~/.codex/auth.json`), so a second
  account (e.g. `CODEX_HOME=~/.codex-cx2`) can be used without touching the
  default login. Adds 2 tests.
- **`GPT2AGENT_RAW_DUMP` heavy-DR diagnostics.** When set, `deep_research_heavy`
  writes every raw SSE object (Phase 1) and conversation-detail poll (Phase 2)
  as JSONL — used to reverse-engineer the real heavy-DR shape.
- Heavy-DR poll backs off ≥300s on HTTP 429 and polls every 120s (was 15s) to
  avoid rate-limiting the conversation endpoint.
- Best-effort heavy-DR citation extraction: `done` pulls
  `content_references` / `search_result_groups` from nested
  `/message/metadata/...` patches or a same-turn conversation-detail node, if
  the backend provides them.

### Known limitations (verified 2026-06-03)

- **Heavy DR does not return a programmatically-fetchable report.** Verified on a
  clean Pro account: `deep_research_heavy` dispatches the
  `connector_openai_deep_research` connector, which renders an "embedded UI
  experience" widget; after a full 30-minute run the conversation's report node
  stayed empty (`content_references: []`, 0-char text) and no `done` event was
  emitted. The report exists only inside the ChatGPT web UI's deep-research
  experience, not in `/backend-api/conversation/{id}`. **Use light mode
  (`deep_research`) for programmatic, cited research.** The best-effort citation
  extraction above is dormant until/unless the backend exposes refs on that path.
- Run heavy/long DR **serially** — concurrent DR + codex jobs on one account
  cause HTTP 429 on the conversation poll. See the deep-research skill's
  "Account limits & concurrency" note.

## [0.0.2] - 2026-05-26

### Renamed — `openai-mcp` → `gpt2agent`

The package, CLI, Python module, default MCP server-name key, and bundled
Claude Code skill are all renamed:

| Was | Now |
|---|---|
| PyPI `openai-mcp` | PyPI `gpt2agent` |
| `pip install openai-mcp` | `pip install gpt2agent` |
| `openai-mcp run --stdio` | `gpt2agent run --stdio` |
| `openai-mcp install` | `gpt2agent install` |
| `from openai_mcp.…` | `from gpt2agent.…` |
| Claude Code key `mcpServers.openai` | `mcpServers.gpt2agent` |
| Codex key `[mcp_servers.openai]` | `[mcp_servers.gpt2agent]` |
| Skill `~/.claude/skills/openai-mcp/` | `~/.claude/skills/gpt2agent/` |
| Config dir `~/.openai-mcp/` | `~/.gpt2agent/` |

**Why:** "openai" is a registered OpenAI® trademark; PyPI may take the
package down under their trademark policy and there's no implied
affiliation. The new name continues the `chatgpt2agent` repo naming
pattern (drop "chat") and reads as "GPT to agent" — i.e. the package
makes any GPT account addressable as an agent.

**Migration for users on 0.0.1 (`openai-mcp`):**
```bash
pipx uninstall openai-mcp
pipx install gpt2agent
gpt2agent install              # registers under new key in client configs
# Optional cleanup:
mv ~/.openai-mcp ~/.gpt2agent  # if you have a config dir from 0.0.1
# Manually remove the stale "openai" entry from ~/.claude.json
# mcpServers (the old binary no longer exists).
```

### Added — one-command install for popular MCP clients

- `gpt2agent install` subcommand — registers gpt2agent with one or more
  MCP-capable agent clients. Targets in 0.0.2:
  - **Claude Code** — writes `~/.claude.json` `mcpServers.gpt2agent` entry
    (preserves all other top-level keys, backs up to `.bak-gpt2agent`).
  - **Codex CLI** — writes `~/.codex/config.toml` `[mcp_servers.gpt2agent]`
    section, preserving all other sections (agents, model config, …).
  - `--client all` (default) auto-detects which clients are installed and
    registers with each.
  - Idempotent: re-running yields the same final config; no duplicate
    sections or entries.
  - `--dry-run` prints what would change without touching files.
  - `--transport http --http-port N` switches to an HTTP entry.
- **Bundled Claude Code skill** at `gpt2agent/skills/deep-research/` —
  ships in the wheel; `gpt2agent install` (or `install --client claude-code`)
  copies it to `~/.claude/skills/deep-research/`. The skill calls
  ConversationClient directly, so it works even before Claude Code restarts.
- **One-line installer** (`install.sh`) — cross-platform replacement of the
  prior macOS-only LaunchAgent script. Pipes through pipx install + codex
  login check + `gpt2agent install`. Curl-pipe-bash friendly.
- **GitHub Actions release workflow** (`.github/workflows/release.yml`) —
  triggers on `v*` tags, verifies the tag matches `pyproject.toml`, runs
  pytest across {ubuntu, macos} × {Python 3.11, 3.13}, builds wheel + sdist,
  publishes to PyPI via OIDC trusted publishing (no token in secrets), and
  creates a GitHub Release with the matching CHANGELOG section as body.
  Auto-marks pre-releases when tag contains `-rc` / `-alpha` / `-beta`.
- **CI workflow** (`.github/workflows/ci.yml`) — runs tests on push/PR to
  main across {ubuntu, macos} × {3.10–3.13}, plus shellcheck on `install.sh`.

### Added — full ChatGPT account surface

- `agent` tool — ChatGPT Agent Mode (262K context, autonomous browsing + code
  execution + tool use). Streams via the same SSE path as `chat` with
  `model=agent-mode`.
- `gpt_chat(gizmo_id, prompt)` tool — chat through one of your private Custom
  GPTs (`g-p-*`). Routes via `gizmo_id` + `conversation_origin` payload fields.
  *Experimental* — field shape reverse-engineered from chatgpt.com web bundle.
- `memory_create_via_chat(content)` tool — workaround for `POST /backend-api/memories`
  returning 405. Asks the model to commit content to memory and relies on
  ChatGPT's model-initiated memory feature.
- `[models].heavy_dr` config key — override the slug used for
  `deep_research_heavy` (default still `gpt-5-5-pro`).
- `[models].agent` config key — override the slug used for `agent` (default
  `agent-mode`).
- `deep_research` / `deep_research_heavy` gained `auto_confirm: bool = True`
  parameter — prefixes an imperative directive so the model starts the
  research without asking "Do you want me to proceed?".
- Token auto-reload: `BackendClient._reload_token_if_stale()` watches the
  mtime of `~/.codex/auth.json` and re-reads on change, so codex's background
  refresh propagates without needing to restart the MCP server. Called before
  every `get()` / `post()`.
- **Multi-turn DR clarification handling** in `ConversationClient.deep_research`.
  ChatGPT's `research` model often opens with a clarifying question instead of
  starting research immediately ("Could you confirm…?"). The wrapper now
  detects clarification-shaped `done` events (short text + question mark, or
  matching phrase list), captures the conversation_id + assistant message id,
  and auto-replies "Proceed with your best interpretation. Do not ask further
  clarifying questions." in the same conversation thread — then continues
  streaming until the real report. Capped at 2 rounds; surface
  `{"type": "clarification_auto_reply", "round": N, "question": text}` events
  so callers can see what happened. Without this, single-turn DR calls
  terminated on the clarification question and never saw real research.

### Fixed

- **heavy DR returned dispatch JSON instead of the real report** — `_emit_done`
  fired on the connector-dispatch envelope (`{"path": ".../connector_openai_deep_research/start", ...}`)
  before the actual report started streaming. Gated with `is_connector_dispatch`
  so the dispatch envelope's `finished_successfully` is suppressed. Real
  report now streams correctly (test: `tests/test_heavy_dr_parser.py`).
- **`Research is not currently supported in temporary chats`** — both DR payload
  builders were forcing `history_and_training_disabled = True`, which marks the
  conversation as Temporary Chat. ChatGPT server then rejected DR. Both DR
  paths now set this field to `False` (regular `chat` keeps `True` for privacy).
- **Quota probe blocked the asyncio event loop** — `init_data = self._backend.post(...)`
  is a synchronous `curl_cffi` call; wrapped in `asyncio.to_thread`.
- **Backend tool registration failures hid the cause** — `server.py` was
  catching `Exception` with `logging.warning` (no traceback). Switched to
  `logging.exception` so import / auth / wiring errors are diagnosable.

### Changed

- README repositioned around the `codex login` story — full account access in
  any MCP client with zero extra credentials.
- Tool table reorganized by category (chat, account, memory, codex).
- Removed dead `image_gen` placeholder from `server.py` (kept as a tracked
  future PR in CHANGELOG instead of in source).
- **25 MCP tools** (up from 19). New tools: `generate_image`, `code_interpreter`,
  `canvas_execute`, `get_conversation`, `get_file_info`, `get_file_download_url`.
- `list_models` returns full metadata: capabilities, enabled_tools, thinking_efforts, tags.
- `list_tasks` returns full metadata: prompt, conversation_id, image_gen_message, interruptions_disabled.
- `conv` singleton passed to tool modules — eliminates redundant sentinel token fetches.
- Image poll loop has exponential backoff (max 5 consecutive errors before raising).
- `temporary` param added to `_build_payload`, `stream`, `complete` — tools that need
  persistent conversations (image gen, code interpreter, canvas, agent, memory) pass `temporary=False`.

### Fixed (post-review)

- `history_and_training_disabled=True` blocked image gen, code interpreter, and canvas —
  new `temporary` param lets tools opt into persistent conversations.
- `tool_call` crashed on SSE frames with `content: null` — null-safety fix (`or {}`).
- `agent()` used `temporary=True`, silently disabling browsing and code execution — now `False`.
- `memory_create_via_chat` used `temporary=True`, preventing memory persistence — now `False`.
- `generate_image` sync HTTP calls blocked the async event loop — wrapped in `asyncio.to_thread`.
- `image_gen` SSE timeout was 120s (too short for complex prompts) — increased to 300s.
- `sediment://` stripping used global `replace` instead of `removeprefix`.
- `tool_call` returned empty text when stream lacked `finished_successfully` —
  added `text_parts` fallback: `last_text or "".join(text_parts)`.
- `conversations.py` syntax error (missing `return`) crashed all tool registration.
- `list_conversations` and `list_tasks` crash on API returning JSON `null` — added `or {}` safety.

## [0.0.1] - 2026-04-24

### Added

- Native Python `/backend-api/conversation` SSE client (no proxy dependency)
- Vendored SHA3-512 proof-of-work + Turnstile solvers (MIT from lanqian528/chat2api)
- 15 MCP tools: `chat`, `deep_research`, `deep_research_heavy`, `account_status`,
  `list_models`, `memory_list`, `memory_search`, `custom_instructions_get`,
  `list_codex_envs`, `list_codex_tasks`, `list_custom_gpts`, `list_conversations`,
  `list_tasks`, `list_apps` (image_gen stub hidden pending implementation)
- Deep Research heavy variant via `/backend-api/f/conversation` +
  `connector:connector_openai_deep_research`
- `curl_cffi` TLS impersonation for Cloudflare + Sentinel bypass
- Codex auth token reuse (`~/.codex/auth.json` → `tokens.access_token`)
- Setup wizard fallback to `~/.openai-mcp/token.json`

### Changed

- Dropped chatgpt2api proxy dependency (was HTTP localhost:9000)
- Dropped openai SDK runtime dependency
- Server is now stdio-first (`openai-mcp run --stdio` for MCP clients)

### Security

- User-Agent / TLS impersonation standardized on Chrome 131
- Session tokens redacted from exception messages
- `history_and_training_disabled=True` by default on all conversation requests
