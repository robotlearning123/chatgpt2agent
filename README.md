# openai-mcp

> **Your `codex login` → full ChatGPT Plus/Pro account inside any MCP client.**

Use your **ChatGPT Plus or Pro** subscription — every model, every account-tier
feature — inside Claude Code, Codex, and any MCP client.

[![PyPI version](https://img.shields.io/pypi/v/openai-mcp)](https://pypi.org/project/openai-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/openai-mcp/)

---

## What it does

openai-mcp exposes **19 MCP tools** that forward requests directly to ChatGPT's backend API.
No proxy process. No separate account. No platform API key. Your `codex login`,
your token, your quota.

If you already have the [`codex`](https://github.com/openai/codex) CLI logged in,
setup is **zero extra steps** — openai-mcp reuses the same `~/.codex/auth.json`
bearer and picks up its background-refreshed token automatically.

Works with Claude Code, Codex CLI, and any client that speaks the MCP protocol over stdio.

---

## Install

```bash
pip install openai-mcp
```

Or with pipx for an isolated install:

```bash
pipx install openai-mcp
```

---

## Setup

```bash
openai-mcp setup
```

The wizard will:

1. Look for an existing Codex auth token at `~/.codex/auth.json`
2. If not found, prompt you to paste a ChatGPT session token
3. Save credentials to `~/.openai-mcp/token.json`

---

## Configure in Claude Code

Add the following to `~/.claude.json` (under `mcpServers`):

```json
{
  "mcpServers": {
    "openai": {
      "type": "stdio",
      "command": "openai-mcp",
      "args": ["run", "--stdio"]
    }
  }
}
```

Restart Claude Code after saving. Tools appear under the `openai` namespace.

---

## Tools (19)

### Chat & reasoning

| Tool | What it does |
|---|---|
| `chat` | Talk to any model on your account (`gpt-5-3` default, override via `model=`). Pass `gpt-5-5-pro`, `o3-pro`, `gpt-5-4-thinking`, … |
| `agent` | **Agent Mode** — 262K context with autonomous browsing, code execution, tool use |
| `deep_research` | Web-augmented research with citations (~30–120 s). Auto-confirms by default |
| `deep_research_heavy` | Long-form DR via `gpt-5-5-pro` + connector (5–30 min, monthly quota). Configurable via `[models].heavy_dr` |
| `gpt_chat` | Talk through one of your private Custom GPTs (`g-p-*`) — *experimental* |

### Account introspection

| Tool | What it does |
|---|---|
| `account_status` | Plan, country, MFA, feature count, subscription expiry |
| `list_models` | All models on your account (slug, max_tokens, reasoning_type) |
| `list_conversations` | Recent ChatGPT conversations (PII redacted) |
| `list_tasks` | Scheduled / completed ChatGPT tasks |
| `list_apps` | Connected apps + connectors |
| `list_custom_gpts` | Your private `g-p-*` GPTs |

### Memory & instructions

| Tool | What it does |
|---|---|
| `memory_list` | List all ChatGPT memory entries (PII redacted) |
| `memory_search` | Keyword filter over memories |
| `memory_create_via_chat` | Add a memory (model-initiated workaround — POST `/memories` is 405) |
| `custom_instructions_get` | Read your current `about_user` / `about_model` |
| `custom_instructions_set` | Update them (read-modify-write, preserves unspecified fields) |

### Codex (cloud agent)

| Tool | What it does |
|---|---|
| `list_codex_envs` | Codex environments (label, repos, network policy) |
| `list_codex_tasks` | Recent Codex tasks + status |
| `codex_task_create` | Kick off a new Codex task (resolves env from `repo_label`) |

---

## Architecture

Native Python implementation — no proxy. The server calls
`/backend-api/conversation` (SSE) directly using `curl_cffi` for TLS
impersonation. Vendored POW and Turnstile solvers handle the OpenAI Sentinel
challenge. Token is reloaded from disk on each request, so codex's background
refresh propagates transparently. See [NOTICES](./NOTICES.md) for attribution.

```
~/.codex/auth.json  (or ~/.openai-mcp/token.json)  ← auto-refreshed by codex
        |
   openai-mcp  (stdio MCP server, token reloaded on each call)
        |
   curl_cffi  →  chatgpt.com /backend-api/{conversation,f/conversation,me,
                                          models, memories, codex, gizmos, ...}
        |
   19 MCP tools  (chat, agent, DR ×2, GPT chat, memory r/w,
                  instructions r/w, codex r/w, account introspect)
```

---

## Configuration

Optional `~/.openai-mcp/config.toml` or `./config.toml`:

```toml
[server]
host = "0.0.0.0"
port = 9000

[models]
chat     = "gpt-5-3"        # default for chat tool
agent    = "agent-mode"     # default for agent tool
heavy_dr = "gpt-5-5-pro"    # override slug for deep_research_heavy
```

---

## Limitations

- **Deep Research quota:** ~248 requests / monthly cycle on Pro; lower on Plus.
- **Account-tier features unavailable in 0.0.2:** Sora video, Operator/CUA, voice
  sessions, image generation (`gpt-image-2`), code interpreter, and canvas
  execution. These use HTTP endpoints that return 404 (Sora/Operator/voice) or
  haven't yet been reverse-engineered out of the chatgpt.com web bundle.
- **`gpt_chat`** is experimental — `gizmo_id` payload field verified against
  web traffic but not load-tested across all g-p-* types.
- Requires an active ChatGPT Plus or Pro subscription.

---

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

---

## License

[MIT](./LICENSE). See [NOTICES](./NOTICES.md) for third-party attributions.

---

## Acknowledgments

- [lanqian528/chat2api](https://github.com/lanqian528/chat2api) — POW and Turnstile solver code (MIT)
- [basketikun/chatgpt2api](https://github.com/basketikun/chatgpt2api) — survey of ChatGPT backend API patterns
- [7836246/cursor2api](https://github.com/7836246/cursor2api) — survey of Cursor API patterns
