# gpt2agent

MCP server exposing full ChatGPT Plus/Pro account features to any MCP client.

## Build & Test

```bash
pytest                    # 129 passed, 9 skipped (live tests gated by SKIP_LIVE)
python -m gpt2agent run   # start MCP server (stdio)
```

## Key Files

- `gpt2agent/server.py` — MCP tool registration (25 tools), config loading
- `gpt2agent/sse.py` — Async SSE client for `/backend-api/conversation` (chat, DR, agent, image gen, code interpreter, canvas)
- `gpt2agent/backend.py` — Sync HTTP client (`curl_cffi`), token management, sentinel challenges
- `gpt2agent/tools/` — 25 MCP tool modules, each with `register(mcp, client, conv=None)`
- `gpt2agent/sentinel.py` — POW + Turnstile solver
- `gpt2agent/install.py` — `gpt2agent install` subcommand

## Critical Invariants

- `temporary=True` sets `history_and_training_disabled=True`, which blocks image gen, code interpreter, canvas, and memory persistence. Tools that need these features MUST pass `temporary=False`.
- Token reloaded from `~/.codex/auth.json` or `~/.gpt2agent/token.json` on each request (mtime check).
- Never commit credentials, tokens, or `.env` files.
- `BackendClient` is synchronous. Async tools must wrap sync calls in `asyncio.to_thread()`.

## Adding Tools

1. Create `gpt2agent/tools/<name>.py` with `register(mcp, client, conv=None)`.
2. Add to `tools/__init__.py` `register_all()`.
3. SSE-based tools: use the `conv` singleton (passed from server.py).
4. REST-based tools: use `client` directly (or `asyncio.to_thread(client.get, ...)` from async handlers).
