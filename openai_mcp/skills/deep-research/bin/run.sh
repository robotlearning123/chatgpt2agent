#!/usr/bin/env bash
# Wrapper around deep_research.py. Picks the right Python (pipx-installed
# openai-mcp venv) and forwards all args.
set -euo pipefail

PYTHON="/home/robot/.local/share/pipx/venvs/openai-mcp/bin/python"
SCRIPT="$(dirname "$(readlink -f "$0")")/deep_research.py"

if [ ! -x "$PYTHON" ]; then
  echo "error: openai-mcp not installed at $PYTHON" >&2
  echo "fix:   pipx install git+https://github.com/robotlearning123/chatgpt2agent.git" >&2
  exit 1
fi
if [ ! -f ~/.codex/auth.json ]; then
  echo "error: ~/.codex/auth.json missing" >&2
  echo "fix:   codex login" >&2
  exit 1
fi

exec "$PYTHON" "$SCRIPT" "$@"
