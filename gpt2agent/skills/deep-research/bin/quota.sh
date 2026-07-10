#!/usr/bin/env bash
# Print remaining ChatGPT Deep Research quota for the selected account.
set -euo pipefail

if command -v gpt2agent >/dev/null 2>&1; then
  PYTHON="$(head -1 "$(command -v gpt2agent)" | sed 's|^#!||' | awk '{print $1}')"
fi
PYTHON="${PYTHON:-$HOME/.local/share/pipx/venvs/gpt2agent/bin/python}"

if [ ! -x "$PYTHON" ]; then
  echo "error: cannot find a Python with gpt2agent installed" >&2
  echo "fix:   pipx install gpt2agent" >&2
  exit 1
fi

exec "$PYTHON" - <<'PY'
import sys

from gpt2agent.backend import BackendClient


def main():
    try:
        b = BackendClient()
        data = b.post(
            "/backend-api/conversation/init",
            json={"conversation_mode_kind": "primary_assistant"},
        )
    except Exception as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print("deep_research quota response is malformed", file=sys.stderr)
        return 1
    limits = data.get("limits_progress") or []
    if not isinstance(limits, list):
        print("deep_research quota response is malformed", file=sys.stderr)
        return 1
    for lim in limits:
        if not isinstance(lim, dict) or lim.get("feature_name") != "deep_research":
            continue
        remaining = lim.get("remaining")
        try:
            if isinstance(remaining, bool):
                raise ValueError
            remaining = int(remaining)
        except (TypeError, ValueError):
            print(
                "deep_research quota remaining is missing or invalid",
                file=sys.stderr,
            )
            return 1
        print(
            f"deep_research remaining = {remaining}  "
            f"reset = {lim.get('reset_after')}"
        )
        return 0

    print("deep_research quota entry not found", file=sys.stderr)
    return 1


raise SystemExit(main())
PY
