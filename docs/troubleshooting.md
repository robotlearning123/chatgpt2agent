# Troubleshooting

### "No ChatGPT token found"

gpt2agent reads, in order, `$CODEX_HOME/auth.json` (or `~/.codex/auth.json`) then
`~/.gpt2agent/token.json`. Fix:

```bash
codex login           # preferred — auto-refreshing token
# or
gpt2agent setup       # paste a ChatGPT token once
```

### MCP tools don't appear in my client

The client only spawns the server on (re)start. **Restart Claude Code / Cursor /
Windsurf / Zed** after `gpt2agent install`. Codex picks it up on its next run.
Confirm the binary works first: `gpt2agent run --stdio` (should start and wait).

### `401 Unauthorized — run codex login`

The bearer token expired. Run `codex login` again (gpt2agent reloads it on the next
call). If you used `gpt2agent setup`, re-run it.

### `403 Forbidden`

A 403 from `/backend-api/conversation` is **not always** an expired token. It can be:
- a Cloudflare / Sentinel bot-check (transient — retry), or
- a region/feature gate on your account.
Try once more; if it persists, re-`codex login`, and check the feature is available
in the ChatGPT web app for your plan.

### `429` / rate limited

You're being throttled. Wait and retry; keep request volume human-scale. Deep
Research also has a monthly quota (see [faq.md](./faq.md)).

### image gen / code interpreter / canvas returns plain text

`chat` defaults to `temporary=True`, which disables tool features. Use the dedicated
tools — `generate_image`, `code_interpreter`, `canvas_execute` — which set
`temporary=False` for you. (Calling `chat` and asking it to make an image won't work.)

### `deep_research_heavy` has no grouped Sources list

The report is recovered from the connector's widget state; grouped source URLs are
usually present but not guaranteed. If absent, the model often cited sources inline
in the body. Use light `deep_research` for reliably grouped citations.

### Installer aborts / `externally-managed-environment`

On PEP-668 systems (Ubuntu/Debian/Fedora) `pip install --user pipx` is blocked.
Install pipx via your distro and re-run the one-liner:

```bash
sudo apt install pipx && pipx ensurepath     # Debian/Ubuntu
sudo dnf install pipx && pipx ensurepath     # Fedora
brew install pipx && pipx ensurepath         # macOS
```

### PyPI install fails (package not found)

The default installer fails closed if the published package cannot be installed;
it never substitutes mutable repository code. Check network/PyPI status and retry
the one-line installer. For development from a checkout you deliberately trust,
use `./install.sh --source /path/to/gpt2agent`.

The installer recreates an existing `gpt2agent` pipx environment when upgrading
so the requested source and a compatible Python are both honored. Re-add any
packages you had deliberately injected into that environment afterward.
