# gpt2agent

> **Your `codex login` → full ChatGPT Plus/Pro account inside any MCP client.**

Use your **ChatGPT Plus or Pro** subscription — every model, every account-tier
feature — inside Claude Code, Codex, and any MCP client.

[![PyPI version](https://img.shields.io/pypi/v/gpt2agent)](https://pypi.org/project/gpt2agent/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/gpt2agent/)

---

## What it does

gpt2agent exposes **25 MCP tools** that forward requests directly to ChatGPT's backend API.
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
| **Claude Code** | `~/.claude.json` | `mcpServers.gpt2agent` (stdio: `gpt2agent run --stdio`) |
| **Codex CLI** | `~/.codex/config.toml` | `[mcp_servers.gpt2agent]` |

Both are idempotent and back up the prior file as `<name>.bak-gpt2agent`.

After running `install`, restart Claude Code so it re-spawns the subprocess.
Codex picks up the new server on its next invocation automatically.

### Manual config (if you'd rather not run install)

Claude Code — add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "gpt2agent": {
      "type": "stdio",
      "command": "gpt2agent",
      "args": ["run", "--stdio"]
    }
  }
}
```

Codex CLI — add to `~/.codex/config.toml`:

```toml
[mcp_servers.gpt2agent]
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

## Tools (25)

### Chat & reasoning

| Tool | What it does |
|---|---|
| `chat` | Talk to any model on your account (`gpt-5-3` default, override via `model=`). Pass `gpt-5-5-pro`, `o3-pro`, `gpt-5-4-thinking`, … |
| `agent` | **Agent Mode** — 262K context with autonomous browsing, code execution, tool use |
| `deep_research` | Web-augmented research with citations (~30–120 s). Auto-confirms by default |
| `deep_research_heavy` | Long-form DR via `gpt-5-5-pro` + connector (5–30 min, monthly quota). Configurable via `[models].heavy_dr` |
| `gpt_chat` | Talk through one of your private Custom GPTs (`g-p-*`) — *experimental* |

### Image & file management

| Tool | What it does |
|---|---|
| `generate_image` | Generate images via ChatGPT's built-in DALL-E. Returns download URLs + metadata |
| `get_file_info` | Metadata for any ChatGPT file (images, uploads) |
| `get_file_download_url` | Temporary download URL for a ChatGPT file (~1h expiry) |

### Code execution

| Tool | What it does |
|---|---|
| `code_interpreter` | Run Python in ChatGPT's sandbox. Returns output + any generated charts/images |
| `canvas_execute` | Execute code via ChatGPT's Canvas feature (live editing environment) |

### Account introspection

| Tool | What it does |
|---|---|
| `account_status` | Plan, country, MFA, feature count, subscription expiry |
| `list_models` | All models on your account (slug, max_tokens, reasoning_type, capabilities, enabled_tools) |
| `list_conversations` | Recent ChatGPT conversations (titles: emails/phones redacted) |
| `get_conversation` | Full message history for a specific conversation (multimodal, code, images) |
| `list_tasks` | Scheduled / completed ChatGPT tasks |
| `list_apps` | Connected apps + connectors |
| `list_custom_gpts` | Your private `g-p-*` GPTs |

### Memory & instructions

| Tool | What it does |
|---|---|
| `memory_list` | List all ChatGPT memory entries (emails/phones redacted) |
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
   25 MCP tools  (chat, agent, DR ×2, GPT chat, image gen,
                  code interpreter, canvas, memory r/w,
                  instructions r/w, codex r/w, account introspect)
```

---

## Configuration

Optional `~/.gpt2agent/config.toml` or `./config.toml`:

```toml
[server]
host = "127.0.0.1"   # loopback only; the HTTP transport is UNAUTHENTICATED
port = 9000

[models]
chat     = "gpt-5-3"        # default for chat tool
agent    = "agent-mode"     # default for agent tool
heavy_dr = "gpt-5-5-pro"    # override slug for deep_research_heavy
```

---

## Limitations

- **Deep Research quota:** roughly ~248 heavy requests / monthly cycle on Pro,
  lower on Plus — approximate and account/region-dependent, not a guaranteed number.
- **Account-tier features not yet supported:** Sora video, Operator/CUA, voice
  sessions. These use HTTP endpoints that return 404 or haven't yet been
  reverse-engineered out of the chatgpt.com web bundle.
- **`gpt_chat`** is experimental — `gizmo_id` payload field verified against
  web traffic but not load-tested across all g-p-* types.
- Requires an active ChatGPT Plus or Pro subscription.

---

## Security & risk — read before you run this

gpt2agent talks to ChatGPT's **private** backend the way the web app does. That
has real consequences; please understand them before pointing it at your account.

- **It impersonates the chatgpt.com web client.** It uses `curl_cffi` TLS
  fingerprint impersonation and vendored Proof-of-Work + Cloudflare Turnstile
  solvers to pass the OpenAI Sentinel challenge. This is **very likely against
  the OpenAI Terms of Service**, and automated/abnormal traffic can get your
  account **rate-limited, challenged, suspended, or banned**. Use an account you
  can afford to lose, keep volume human-scale, and don't rely on it for anything
  critical. This is a reverse-engineering / research tool, not an official API.
- **The HTTP transport is UNAUTHENTICATED.** It proxies your *entire* account —
  read all conversations, spend Deep Research quota, overwrite custom
  instructions, launch Codex cloud tasks. Anyone who can reach the port controls
  your account. Therefore:
  - **Use stdio** (the default for `gpt2agent install`) for local clients like
    Claude Code and Codex. It is not network-exposed.
  - The server **binds `127.0.0.1` by default** and **refuses** to start the HTTP
    transport on a non-loopback host unless you explicitly set
    `GPT2AGENT_ALLOW_REMOTE=1`. Only do that behind your own auth proxy / firewall.
- **Your token stays local.** It is read from `~/.codex/auth.json` (or
  `~/.gpt2agent/token.json`, chmod `600`) and sent only to `chatgpt.com`.
  gpt2agent never transmits it anywhere else. Token/secret values are redacted
  from error messages and logs (best-effort).
- **PII redaction is limited.** Tools that return conversation/memory data strip
  only **emails and phone numbers** from text — names, addresses, IDs, and the
  full message bodies of `get_conversation` are returned verbatim. Don't treat
  the output as anonymized.
- **`GPT2AGENT_RAW_DUMP`** (debug) writes raw, unredacted SSE/poll traffic —
  including prompts, responses, and resume tokens — to the path you give it.
  Use only for debugging and delete the dumps after.

Found a security issue? See [SECURITY.md](./SECURITY.md).

---

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

### Release

Tagged releases are configured to publish to PyPI and create a GitHub Release
with the matching CHANGELOG section:

```bash
# bump version
$EDITOR pyproject.toml             # e.g. "0.0.3" → "0.0.4"
$EDITOR CHANGELOG.md               # add ## [0.0.4] - YYYY-MM-DD ...
git commit -am "release: 0.0.4"
git tag v0.0.4
git push origin main --tags        # release workflow fires on the tag
```

The release workflow (`.github/workflows/release.yml`) verifies the tag
matches `pyproject.toml`, runs the test matrix, builds wheel + sdist, publishes
to PyPI via OIDC trusted publishing, and posts a GitHub Release with that
version's CHANGELOG body.

> **One-time PyPI setup required before the first publish succeeds.** PyPI's
> OIDC exchange needs a Trusted Publisher registered for this repo (project
> `gpt2agent`, owner `robotlearning123`, workflow `release.yml`, environment
> `pypi`) at
> [pypi.org → Publishing](https://pypi.org/manage/account/publishing/) — or a
> first manual `twine upload` to create the project. Until that is done the
> release job fails with `invalid-publisher` and the package is not on PyPI;
> the `install.sh` one-liner falls back to a `git+https` install in the meantime.

---

## License

[MIT](./LICENSE). See [NOTICES](./NOTICES.md) for third-party attributions.

---

## Acknowledgments

- [lanqian528/chat2api](https://github.com/lanqian528/chat2api) — POW and Turnstile solver code (MIT)
- [basketikun/chatgpt2api](https://github.com/basketikun/chatgpt2api) — survey of ChatGPT backend API patterns
- [7836246/cursor2api](https://github.com/7836246/cursor2api) — survey of Cursor API patterns
