# Contributing to gpt2agent

## Prerequisites

- Python 3.10+
- pipx
- codex CLI (for live testing against real backend)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Tests

```bash
pytest
```

38 tests, 9 skipped. All must pass before merging.

## Code style

- Follow existing patterns in the codebase.
- No comments unless the WHY is non-obvious.
- No docstrings longer than one short line.
- Minimal changes — don't refactor surrounding code.

## PR process

- One concern per PR.
- Conventional commits: `feat(scope):`, `fix(scope):`, `test:`, `docs:`, `chore:`.
- Tests required for any new behavior.
- Squash-merge into main.

## Adding a new MCP tool

1. Create `gpt2agent/tools/<name>.py` with a `register(mcp, client: BackendClient)` function.
2. For tools that need SSE streaming (chat, image gen, etc.), accept an optional `conv` param: `register(mcp, client, conv=None)`.
3. Add the import to `gpt2agent/tools/__init__.py` and call `register()` in `register_all()`.
4. Add tests in `tests/`.

## Architecture

- `BackendClient` (backend.py): synchronous HTTP via `curl_cffi`. Handles token loading, sentinel challenges, REST endpoints.
- `ConversationClient` (sse.py): async SSE streaming. Handles `/backend-api/conversation` and `/backend-api/f/conversation` for chat, DR, agent mode, image gen, code interpreter, canvas.
- `server.py`: FastMCP tool registration. Creates `BackendClient` + `ConversationClient` singletons.
- `tools/`: 25 MCP tool modules, each with a `register()` function.

The `temporary` parameter on `_build_payload()` controls `history_and_training_disabled`. Tools that use ChatGPT features (image gen, code interpreter, canvas, memory writes, agent mode) MUST pass `temporary=False`.

## Token

Loaded from `~/.codex/auth.json` (preferred, auto-refreshed by codex) or `~/.gpt2agent/token.json` (manual). Never commit tokens or credentials.
