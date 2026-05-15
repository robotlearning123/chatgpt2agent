# Changelog

All notable changes to this project will be documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning: [SemVer](https://semver.org/).

## [0.0.2] - 2026-05-15

### Added

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
