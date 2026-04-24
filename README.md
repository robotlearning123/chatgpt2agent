# chatgpt-pro-mcp

An MCP server that exposes **ChatGPT Pro models** to Claude Code and any other MCP client — one running process, shared by all agents.

> **Personal use only.** See [Disclaimer](#disclaimer) before using.

## What it does

Wraps an OpenAI-compatible API (e.g. [chatgpt2api](https://github.com/lanqian528/chat2api)) and serves three tools over HTTP:

| Tool | Model | Use for |
|------|-------|---------|
| `ask_gpt_pro` | gpt-5-5-pro (default), gpt-5-4-pro, o3-pro, gpt-5-5-thinking | Reasoning, code, long-context |
| `deep_research` | research | Web search + synthesis with citations |
| `gpt_image_gen` | gpt-image-2 | Image generation (returns base64 PNG) |

## Requirements

- Python 3.10+
- A running OpenAI-compatible API pointed at your ChatGPT Pro account  
  → [chatgpt2api](https://github.com/lanqian528/chat2api) works well for this

## Quick start

```bash
git clone https://github.com/robotlearning123/chatgpt-pro-mcp
cd chatgpt-pro-mcp
pip install -r requirements.txt

# Run (HTTP mode, default port 9000)
CHATGPT_BASE_URL=http://localhost:3001/v1 \
CHATGPT_API_KEY=your-key \
python3 server.py
```

## macOS auto-start

```bash
bash install.sh   # interactive — prompts for URL, key, port
```

Installs a LaunchAgent that keeps the server alive across reboots.

## Connect to Claude Code

Add to `~/.claude.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "chatgpt-pro": {
      "type": "url",
      "url": "http://localhost:9000/mcp"
    }
  }
}
```

Restart Claude Code. Tools appear as `mcp__chatgpt-pro__ask_gpt_pro`, etc.

## Connect from any HTTP client

The server speaks [MCP streamable-http](https://spec.modelcontextprotocol.io/specification/basic/transports/).  
Quick smoke-test:

```bash
curl http://localhost:9000/mcp \
  -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `CHATGPT_BASE_URL` | `http://localhost:3001/v1` | OpenAI-compatible base URL |
| `CHATGPT_API_KEY` | `sk-placeholder` | API key |
| `MCP_HOST` | `0.0.0.0` | Bind host |
| `MCP_PORT` | `9000` | Bind port |

## stdio mode (legacy)

```bash
python3 server.py --stdio
```

```json
{
  "mcpServers": {
    "chatgpt-pro": {
      "type": "stdio",
      "command": "python3",
      "args": ["/path/to/server.py", "--stdio"],
      "env": {
        "CHATGPT_BASE_URL": "http://localhost:3001/v1",
        "CHATGPT_API_KEY": "your-key"
      }
    }
  }
}
```

---

## Disclaimer

**This project is intended for personal, non-commercial use only.**

- This tool is a local MCP bridge. It does **not** bypass, crack, or redistribute OpenAI's API — it connects to an OpenAI-compatible backend using credentials you own.
- You are solely responsible for ensuring your usage complies with [OpenAI's Terms of Service](https://openai.com/policies/terms-of-use) and the terms of any backend service you connect it to.
- **Do not** use this tool to resell API access, serve third parties, or operate a commercial service.
- **Do not** share your API keys publicly or expose the server to the open internet without authentication.
- The authors provide this software as-is, with no warranty of any kind. Use at your own risk.

This project is not affiliated with, endorsed by, or sponsored by OpenAI or Anthropic.

## License

[MIT](LICENSE) — free for personal use. Commercial use is not permitted.
