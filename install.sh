#!/usr/bin/env bash
# openai-mcp — one-line installer.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/robotlearning123/chatgpt2agent/main/install.sh | bash
#   ./install.sh                                          # from a checkout
#   ./install.sh --client claude-code                     # install for one client only
#   ./install.sh --transport http --port 9000             # use HTTP transport
#   ./install.sh --no-skill                               # skip the deep-research skill
#   ./install.sh --no-register                            # install package only; skip client wiring
#   ./install.sh --source <path-or-git-url>               # install from a local path or git URL
#
# Steps:
#   1. Ensure Python 3.10+ and pipx are available.
#   2. pipx install openai-mcp (from PyPI by default).
#   3. codex login check (auth via ~/.codex/auth.json — no platform API key).
#   4. openai-mcp install --client <X>   # register with detected MCP clients + drop skill.
set -euo pipefail

GREEN=$'\033[92m'; YELLOW=$'\033[93m'; RED=$'\033[91m'; BOLD=$'\033[1m'; RESET=$'\033[0m'
ok()   { printf "  ${GREEN}✓${RESET} %s\n" "$*"; }
info() { printf "  ${YELLOW}→${RESET} %s\n" "$*"; }
err()  { printf "  ${RED}✗${RESET} %s\n" "$*" >&2; }
h1()   { printf "\n${BOLD}%s${RESET}\n" "$*"; }

CLIENT="all"
TRANSPORT="stdio"
PORT="9000"
SKILL_FLAG=""
REGISTER=1
SOURCE="openai-mcp"  # default: PyPI

while [[ $# -gt 0 ]]; do
  case "$1" in
    --client)       CLIENT="$2"; shift 2 ;;
    --transport)    TRANSPORT="$2"; shift 2 ;;
    --port)         PORT="$2"; shift 2 ;;
    --no-skill)     SKILL_FLAG="--no-skill"; shift ;;
    --no-register)  REGISTER=0; shift ;;
    --source)       SOURCE="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) err "Unknown option: $1"; exit 2 ;;
  esac
done

h1 "openai-mcp installer"

# --- 1. Python 3.10+ -------------------------------------------------------

PYTHON=""
for cand in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PYTHON="$cand"
      break
    fi
  fi
done

if [[ -z "$PYTHON" ]]; then
  err "Python 3.10+ required. Install via your package manager (e.g. brew install python@3.12)."
  exit 1
fi
ok "Python: $($PYTHON --version) ($(command -v "$PYTHON"))"

# --- 2. pipx ----------------------------------------------------------------

if ! command -v pipx >/dev/null 2>&1; then
  info "pipx not found; installing via $PYTHON -m pip install --user pipx"
  "$PYTHON" -m pip install --user --quiet pipx
  "$PYTHON" -m pipx ensurepath >/dev/null 2>&1 || true
  # Refresh PATH for this shell so the next call finds pipx.
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) export PATH="$HOME/.local/bin:$PATH" ;;
  esac
fi

if ! command -v pipx >/dev/null 2>&1; then
  err "pipx still not on PATH. Open a new shell (PATH refresh) and re-run, or install pipx manually."
  exit 1
fi
ok "pipx: $(pipx --version 2>/dev/null || echo present)"

# --- 3. install openai-mcp -------------------------------------------------

if [[ -d "$SOURCE" ]]; then
  info "Installing (editable) from $SOURCE"
  pipx install --editable --force "$SOURCE"
elif [[ "$SOURCE" == git+* || "$SOURCE" == http* ]]; then
  info "Installing from $SOURCE"
  pipx install --force "$SOURCE"
else
  info "Installing $SOURCE from PyPI"
  if ! pipx install --force "$SOURCE" 2>&1; then
    err "PyPI install failed. If the release isn't published yet, run:"
    err "  $0 --source git+https://github.com/robotlearning123/chatgpt2agent.git"
    exit 1
  fi
fi

if ! command -v openai-mcp >/dev/null 2>&1; then
  err "openai-mcp not on PATH after install. Open a new shell and re-run."
  exit 1
fi
ok "openai-mcp installed"

# --- 4. codex login check --------------------------------------------------

if [[ -f "$HOME/.codex/auth.json" ]]; then
  ok "codex token found at ~/.codex/auth.json (no extra login needed)"
else
  info "No ~/.codex/auth.json yet. Install codex CLI and run \`codex login\`:"
  info "  https://github.com/openai/codex#installation"
  info "  (or run \`openai-mcp setup\` to paste a token manually)"
fi

# --- 5. register with clients ----------------------------------------------

if [[ $REGISTER -eq 1 ]]; then
  ARGS=(install --client "$CLIENT" --transport "$TRANSPORT" --http-port "$PORT")
  if [[ -n "$SKILL_FLAG" ]]; then ARGS+=("$SKILL_FLAG"); fi
  openai-mcp "${ARGS[@]}"
else
  info "Skipping client registration (--no-register). Run later:"
  info "  openai-mcp install --client $CLIENT"
fi

h1 "Done."
echo "  Try:  openai-mcp run --stdio   (manual smoke test)"
echo "  Or restart your MCP client (Claude Code / Codex) so it picks up the new server."
