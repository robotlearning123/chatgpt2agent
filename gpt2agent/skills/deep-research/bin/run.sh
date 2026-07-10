#!/usr/bin/env bash
# Wrapper around deep_research.py. Finds a Python with gpt2agent installed
# (pipx, pip --user, or any venv where the `gpt2agent` CLI is on PATH).
set -euo pipefail

if command -v gpt2agent >/dev/null 2>&1; then
  PYTHON="$(head -1 "$(command -v gpt2agent)" | sed 's|^#!||' | awk '{print $1}')"
fi
PYTHON="${PYTHON:-$HOME/.local/share/pipx/venvs/gpt2agent/bin/python}"
# Empty CDPATH is intentional so cd cannot print a lookup-path match.
# shellcheck disable=SC1007
SCRIPT_DIR="$(CDPATH= cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$SCRIPT_DIR/deep_research.py"
CODEX_AUTH="${CODEX_HOME:-$HOME/.codex}/auth.json"
SAVED_AUTH="$HOME/.gpt2agent/token.json"

if [ ! -x "$PYTHON" ]; then
  echo "error: cannot find a Python with gpt2agent installed" >&2
  echo "       (looked at: \$PATH gpt2agent CLI shebang, then $HOME/.local/share/pipx/venvs/gpt2agent/bin/python)" >&2
  echo "fix:   pipx install gpt2agent" >&2
  exit 1
fi
if [ ! -f "$CODEX_AUTH" ] && [ ! -f "$SAVED_AUTH" ]; then
  echo "error: no ChatGPT auth file found" >&2
  echo "       checked: $CODEX_AUTH and $SAVED_AUTH" >&2
  echo "fix:   run codex login or gpt2agent setup" >&2
  exit 1
fi
exec "$PYTHON" "$SCRIPT" "$@"
