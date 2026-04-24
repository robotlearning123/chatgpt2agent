# openai-mcp

Use your **ChatGPT Plus or Pro** subscription inside Claude Code, Codex, and other AI coding tools.

One command to set up. Works in the background. Your account, your quota.

---

## Quick start

```bash
pip install git+https://github.com/robotlearning123/chatgpt2agent.git
openai-mcp setup
```

That's it. The setup wizard will:

1. Log you into ChatGPT (opens your browser)
2. Detect your plan (Plus or Pro)
3. Start a local server
4. Register it with Claude Code automatically

Restart Claude Code when done.

---

## What you get

Tools available inside Claude Code after setup:

| Tool | What it does | Plan |
|------|-------------|------|
| `chat` | Chat with GPT-4o, GPT-5, o3-pro and more | Plus + Pro |
| `deep_research` | Web search + synthesized report with citations | Plus + Pro |
| `image_gen` | Generate images with gpt-image-2 | Pro only |

**Example prompts in Claude Code:**

> *"Use deep_research to find recent papers on diffusion transformers"*
>
> *"Use chat with model gpt-5-5-pro to review this architecture"*
>
> *"Use image_gen to create a diagram of this system"*

---

## Requirements

- Python 3.10+
- A ChatGPT Plus ($20/mo) or Pro ($200/mo) subscription
- Claude Code, Codex CLI, or any MCP-compatible agent

---

## How it works

```
Your ChatGPT account
        ↓
  local gateway  :3001   (handles auth, talks to ChatGPT)
        ↓
   MCP server    :9000   (Claude Code connects here)
        ↓
  Claude Code tools: chat / deep_research / image_gen
```

Everything runs locally on your machine. No data leaves except to OpenAI/ChatGPT — the same as using ChatGPT directly.

The server starts automatically at login (macOS LaunchAgent) and restarts if it crashes.

---

## Connecting other tools

**Any MCP client** — add this to its config:

```json
{
  "mcpServers": {
    "openai": {
      "type": "url",
      "url": "http://localhost:9000/mcp"
    }
  }
}
```

**Any HTTP client / Python script:**

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:3001/v1",
    api_key="openai-mcp-local"
)
resp = client.chat.completions.create(
    model="gpt-5-5-pro",
    messages=[{"role": "user", "content": "Hello"}]
)
```

---

## Commands

```bash
openai-mcp setup          # First-time setup (login + register)
openai-mcp run            # Start server manually
openai-mcp run --stdio    # stdio mode (Claude Code legacy config)
```

---

## Troubleshooting

**"Tools not showing in Claude Code"** → Restart Claude Code after setup.

**"Login failed / token expired"** → Re-run `openai-mcp setup`. It refreshes your token.

**"deep_research not available"** → Requires ChatGPT Plus or Pro plan.

**Check logs:**
```bash
tail -f ~/.openai-mcp/mcp.log
tail -f ~/.openai-mcp/chatgpt2api.log
```

**Restart server:**
```bash
launchctl stop com.user.openai-mcp
launchctl start com.user.openai-mcp
```

---

## Disclaimer

**Personal, non-commercial use only.**

This tool runs on your own machine using your own ChatGPT account. It does not bypass or resell OpenAI's services. You are responsible for complying with [OpenAI's Terms of Service](https://openai.com/policies/terms-of-use).

Do not expose the local server to the internet or share your token.

Not affiliated with OpenAI or Anthropic.

## License

[MIT](LICENSE) — personal use only, commercial use not permitted.
