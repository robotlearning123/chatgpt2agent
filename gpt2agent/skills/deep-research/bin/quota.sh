#!/usr/bin/env bash
# Print remaining ChatGPT Pro Deep Research quota.
set -euo pipefail

if command -v gpt2agent >/dev/null 2>&1; then
  PYTHON="$(head -1 "$(command -v gpt2agent)" | sed 's|^#!||' | awk '{print $1}')"
fi
PYTHON="${PYTHON:-$HOME/.local/share/pipx/venvs/gpt2agent/bin/python}"

if [ ! -x "$PYTHON" ]; then
  echo "error: cannot find a Python with gpt2agent installed" >&2
  echo "fix:   pipx install git+https://github.com/robotlearning123/gpt2agent.git" >&2
  exit 1
fi

exec "$PYTHON" - <<'PY'
from gpt2agent.backend import BackendClient
b = BackendClient()
try:
    data = b.post("/backend-api/conversation/init", json={"conversation_mode_kind": "primary_assistant"})
    for lim in (data.get("limits_progress") or []):
        if isinstance(lim, dict) and lim.get("feature_name") == "deep_research":
            print(f"deep_research remaining = {lim.get('remaining')}  reset = {lim.get('reset_after')}")
            break
    else:
        print("deep_research quota entry not found")
except Exception as e:
    print(f"error: {type(e).__name__}: {e}")
PY
