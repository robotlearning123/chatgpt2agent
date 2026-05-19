# gpt2agent

> **Your `codex login` → full ChatGPT Plus/Pro account inside any MCP client.**

Use your **ChatGPT Plus or Pro** subscription — every model, every account-tier
feature — inside Claude Code, Codex, and any MCP client.

[![PyPI version](https://img.shields.io/pypi/v/gpt2agent)](https://pypi.org/project/gpt2agent/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/gpt2agent/)

---

## What it does

gpt2agent exposes **19 MCP tools** that forward requests directly to ChatGPT's backend API.
No proxy process. No separate account. No platform API key. Your `codex login`,
your token, your quota.

If you already have the [`codex`](https://github.com/openai/codex) CLI logged in,
setup is **zero extra steps** — gpt2agent reuses the same `~/.codex/auth.json`
bearer and picks up its background-refreshed token automatically.

Works with Claude Code, Codex CLI, and any client that speaks the MCP protocol over stdio.

---

## Install — one line

```bash
curl -fsSL https://raw.githubusercontent.com/robotlearning123/gpt2agent/main/install.sh | bash
```

That command:
1. Installs `gpt2agent` via pipx (creates an isolated env).
2. Reuses your existing `~/.codex/auth.json` if you've run `codex login` — no separate ChatGPT token paste needed.
3. Detects which MCP clients you have (Claude Code, Codex) and writes the right config snippet for each.
4. Drops the `deep-research` Claude Code skill into `~/.claude/skills/`.

### Or step-by-step

```bash
# 1. Install the package globally (isolated venv)
pipx install gpt2agent

# 2. Register with all detected MCP clients (Claude Code, Codex)
gpt2agent install                          # auto-detect everything

# Want only one client?
gpt2agent install --client claude-code
gpt2agent install --client codex

# HTTP transport instead of stdio?
gpt2agent install --transport http --http-port 9000
```

### Per-client config

The `install` subcommand writes the right thing for each:

| Client | File | Section |
|---|---|---|
| **Claude Code** | `~/.claude.json` | `mcpServers.openai` (stdio: `gpt2agent run --stdio`) |
| **Codex CLI** | `~/.codex/config.toml` | `[mcp_servers.openai]` |

Both are idempotent and back up the prior file as `<name>.bak-gpt2agent`.

After running `install`, restart Claude Code so it re-spawns the subprocess.
Codex picks up the new server on its next invocation automatically.

### Manual config (if you'd rather not run install)

Claude Code — add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "openai": {
      "type": "stdio",
      "command": "gpt2agent",
      "args": ["run", "--stdio"]
    }
  }
}
```

Codex CLI — add to `~/.codex/config.toml`:

```toml
[mcp_servers.openai]
command = "gpt2agent"
args = ["run", "--stdio"]
```

---

## Setup (manual token paste — only if codex isn't available)

```bash
gpt2agent setup
```

Prompts for a ChatGPT session token and saves it to `~/.gpt2agent/token.json`.
The `codex login` flow is preferred when available because codex auto-refreshes
its token; gpt2agent reloads `~/.codex/auth.json` on mtime change so long
calls don't 401 mid-flight.

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
~/.codex/auth.json  (or ~/.gpt2agent/token.json)  ← auto-refreshed by codex
        |
   gpt2agent  (stdio MCP server, token reloaded on each call)
        |
   curl_cffi  →  chatgpt.com /backend-api/{conversation,f/conversation,me,
                                          models, memories, codex, gizmos, ...}
        |
   19 MCP tools  (chat, agent, DR ×2, GPT chat, memory r/w,
                  instructions r/w, codex r/w, account introspect)
```

---

## Configuration

Optional `~/.gpt2agent/config.toml` or `./config.toml`:

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

### Release

Tagged releases auto-publish to PyPI and create a GitHub Release with the
matching CHANGELOG section:

```bash
# bump version
$EDITOR pyproject.toml             # e.g. "0.0.2" → "0.0.3"
$EDITOR CHANGELOG.md               # add ## [0.0.3] - YYYY-MM-DD ...
git commit -am "release: 0.0.3"
git tag v0.0.3
git push origin main --tags        # release workflow fires on the tag
```

The release workflow (`.github/workflows/release.yml`) verifies the tag
matches `pyproject.toml`, runs the test matrix, builds wheel + sdist, publishes
to PyPI via OIDC trusted publishing (no token in secrets — one-time setup at
[pypi.org/manage/account/publishing](https://pypi.org/manage/account/publishing/)),
and posts a GitHub Release with that version's CHANGELOG body.

---

## License

[MIT](./LICENSE). See [NOTICES](./NOTICES.md) for third-party attributions.

---

## Acknowledgments

- [lanqian528/chat2api](https://github.com/lanqian528/chat2api) — POW and Turnstile solver code (MIT)
- [basketikun/chatgpt2api](https://github.com/basketikun/chatgpt2api) — survey of ChatGPT backend API patterns
- [7836246/cursor2api](https://github.com/7836246/cursor2api) — survey of Cursor API patterns
