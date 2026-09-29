#!/usr/bin/env bash
# Preview is now the default. See --help before applying a pinned update.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
exec python3 "$HERE/fleet_sync.py" "$@"
