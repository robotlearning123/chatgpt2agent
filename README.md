# openai-mcp

Use your **ChatGPT Plus or Pro** subscription inside Claude Code, Codex, and any MCP client.

[![PyPI version](https://img.shields.io/pypi/v/openai-mcp)](https://pypi.org/project/openai-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/openai-mcp/)

---

## What it does

openai-mcp exposes 15 MCP tools that forward requests directly to ChatGPT's backend API.
No proxy process. No separate account. Your token, your quota.

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

## Tools

| Tool | What it does |
|---|---|
| `chat` | Chat with GPT-5.x, Pro models, o3, o3-pro |
| `deep_research` | Web-augmented search answer (~30 s) |
| `deep_research_heavy` | Long-form Deep Research via gpt-5-5-pro (5–30 min, uses monthly quota) |
| `account_status` | ChatGPT plan and enabled features |
| `list_models` | All models available to your account |
| `memory_list` | List ChatGPT memories (PII redacted) |
| `memory_search` | Search ChatGPT memories by keyword |
| `custom_instructions_get` | Retrieve your ChatGPT custom instructions |
| `list_codex_envs` | List Codex environments |
| `list_codex_tasks` | List recent Codex tasks |
| `list_custom_gpts` | List your custom GPTs |
| `list_conversations` | Recent ChatGPT conversations |
| `list_tasks` | Scheduled ChatGPT tasks |
| `list_apps` | Connected apps and connectors |

---

## Architecture

Native Python implementation — no proxy. The server calls
`/backend-api/conversation` (SSE) directly using `curl_cffi` for TLS
impersonation. Vendored POW and Turnstile solvers handle the OpenAI Sentinel
challenge. See [NOTICES](./NOTICES.md) for attribution.

```
~/.codex/auth.json  (or ~/.openai-mcp/token.json)
        |
   openai-mcp  (stdio MCP server)
        |
   curl_cffi  →  chatgpt.com /backend-api/conversation  (SSE)
        |
   14 read tools + 1 heavy DR tool
```

---

## Limitations

- **Deep Research quota:** 248 requests/month on Pro; lower on Plus.
- **image_gen:** stub is present but not yet wired to a working endpoint.
- **memory_add:** read-only — the write endpoint returns 405; tool is not registered.
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
