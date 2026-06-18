# FAQ

### Is this official / affiliated with OpenAI?

No. gpt2agent is an independent, unofficial project. It talks to ChatGPT's private
backend the way the web client does (TLS impersonation + the Sentinel
proof-of-work/Turnstile challenge). There is no official API behind it.

### Will this get my account banned?

It might. Using a reverse-engineered client likely violates the OpenAI Terms of
Service, and automated/abnormal traffic can get an account rate-limited,
challenged, suspended, or banned. Use an account you can afford to lose, keep
volume human-scale, and don't depend on it for anything critical. See the README's
**Security & risk** section.

### Why stdio instead of HTTP?

stdio runs the server as a local subprocess of your client — nothing is exposed on
the network. The HTTP transport has **no authentication** and proxies your entire
account, so it binds loopback only and refuses non-loopback hosts unless you opt in
with `GPT2AGENT_ALLOW_REMOTE=1`. Prefer stdio.

### Plus vs Pro — what's the difference?

Both work. Pro unlocks the heavier models (e.g. `gpt-5-5-pro`, `o3-pro`) and a
larger monthly Deep Research quota. Run `list_models` to see exactly what your
account has, and `account_status` for your plan.

### How much Deep Research can I run?

Roughly ~248 heavy requests per monthly cycle on Pro, fewer on Plus — approximate
and account/region-dependent, not a guaranteed number. Light `deep_research` is
cheaper. Run heavy DR serially.

### Is `gpt_chat` (Custom GPTs) stable?

It's **experimental**. Pass the `short_url` returned by `list_custom_gpts` as the
`gizmo_id`. The payload field is reverse-engineered and not load-tested across all
Custom GPT types.

### Where does my token go?

It's read locally from `~/.codex/auth.json` (codex login) or
`~/.gpt2agent/token.json` (mode `600`) and sent only to `chatgpt.com`. gpt2agent
never transmits it anywhere else, and redacts token/secret values from error output.

### What's NOT supported?

Sora video, Operator/CUA, and voice sessions — those endpoints aren't reverse-engineered
yet. Everything else (chat, agent mode, deep research, image gen, code interpreter,
canvas, memory, custom instructions, Codex tasks) is exposed via the 25 MCP tools.
