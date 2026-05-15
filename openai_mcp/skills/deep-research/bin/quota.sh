#!/usr/bin/env bash
# Print remaining ChatGPT Pro Deep Research quota.
set -euo pipefail
PYTHON="/home/robot/.local/share/pipx/venvs/openai-mcp/bin/python"
exec "$PYTHON" - <<'PY'
from openai_mcp.backend import BackendClient
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
