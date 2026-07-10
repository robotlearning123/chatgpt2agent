#!/usr/bin/env bash
# Wrapper around deep_research.py. Finds a Python with gpt2agent installed
# (pipx, pip --user, or any venv where the `gpt2agent` CLI is on PATH).
set -euo pipefail

if command -v gpt2agent >/dev/null 2>&1; then
  PYTHON="$(head -1 "$(command -v gpt2agent)" | sed 's|^#!||' | awk '{print $1}')"
fi
PYTHON="${PYTHON:-$HOME/.local/share/pipx/venvs/gpt2agent/bin/python}"
SCRIPT="$(dirname "$(readlink -f "$0")")/deep_research.py"
AUTH_FILE="${CODEX_HOME:-$HOME/.codex}/auth.json"

if [ ! -x "$PYTHON" ]; then
  echo "error: cannot find a Python with gpt2agent installed" >&2
  echo "       (looked at: \$PATH gpt2agent CLI shebang, then $HOME/.local/share/pipx/venvs/gpt2agent/bin/python)" >&2
  echo "fix:   pipx install git+https://github.com/robotlearning123/gpt2agent.git" >&2
  exit 1
fi
if [ ! -f "$AUTH_FILE" ]; then
  echo "error: $AUTH_FILE missing" >&2
  echo "fix:   codex login" >&2
  exit 1
fi

exec "$PYTHON" "$SCRIPT" "$@"
