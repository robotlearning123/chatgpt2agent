# Changelog

All notable changes to this project will be documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning: [SemVer](https://semver.org/).

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
