# GPT-Live → Coding-Agent Bridge Layer — spec (v0.0.14)

> One-page contract for "the layer" between GPT-Live and our coding agent.
> Anchored on the empirical protocol (`2026-07-11-gpt-live-{full-pipeline,protocol-spec}.md`).
> Direction is **human → agent** only. Owner-clarified 2026-07-11.

## Goal / non-goals

**Goal.** A human talks to GPT-Live (real-time voice). A thin middleware **layer**
taps the human side of the live conversation, routes each real utterance to a
pluggable **coding agent** (Claude / gpt2agent / codex), and surfaces the agent's
reply back to the human **out-of-band** (text overlay / side UI). GPT-Live keeps
serving its own real-time answers + background resources (search, code, memory,
canvas); the layer adds our coding agent as an extra backend brain.

**Structural symmetry (design north-star).** GPT-Live already IS a real-time voice
front-end backed by a rich resource brain — `human ⇄ [ChatGPT: search/code/memory/
canvas]`. Our layer mirrors that shape with OUR brain — `human ⇄ GPT-Live(voice) ⇄
[coding agent: repo/shell/MCP tools/codex/memory]`. Not identical (ours is a coding
agent with real repo + tool access), but the same pattern: a resource-backed brain
made voice-accessible. The layer is what turns our agent into that brain; it is not a
dumb transcript pipe.

**Non-goals.**
- ❌ Making GPT-Live *speak* the agent's reply. The consumer datachannel silently
  drops all client-injected speak/response events (`response.create`,
  `conversation.item.create`, `session.update` — verified). **No agent→Live write
  channel.** Reply reaches the human out-of-band, not through Live's voice.
- ❌ Headless / fake-mic as a product path. Synthetic audio is not transcribed by
  Live; only a real mic is. Fake-mic + puppeteer is a **CI/test harness only**.
- ❌ Any Cloudflare Turnstile / bot-detection bypass. The real, signed-in headed
  Chrome clears it natively; that is the only supported auth path.

## Architecture

```
 human ⇄ GPT-Live (real Chrome, real mic, signed-in)
              │  datachannel: chat_message_delta / spawn_update / usage_update  (audio never leaves browser)
              ▼
 ① TAP        extension/hook.js  → TranscriptAssembler (transcript.mjs)
              │  emits structured events: {human_utterance}
              ▼
 ② LAYER      the bridge (src/export.mjs = BridgeLayer)
              ├─ state:  turn/session buffer (text only)
              ├─ policy: isActionable() (drop acks/filler)
              ├─ adapter: onUserSaid(text) → coding agent   (agent-gateway.mjs / --agent-cmd)
              └─ egress: reply → human via overlay/side-UI   (NOT into Live)
              ▼
 ③ AGENT      coding agent (repo + tools) — the brain
```

## Interfaces (frozen for v0.0.14)

**Layer ingress (from TAP).** `BridgeLayer.ingest(rawDatachannelMessage) →
{ humanText: string|null }`. Parses the real consumer protocol via
`TranscriptAssembler`; returns a completed human utterance (`direction:"in"`) or null.
Filler/acks dropped by `isActionable`.

**Layer → agent adapter.** `onUserSaid(humanText) → Promise<string|null>`. Pluggable.
Default = `agent-gateway.mjs` running `AGENT_CMD` (`claude -p` / `codex exec`).

**Layer egress (to human).** `onReply(text)` → text overlay on the Live page (extension)
or console (test harness). Never sent to the Live datachannel.

**Control plane (localhost, observe + lifecycle; text only).**
`GET /status` · `GET /transcript[?clear=1]` · `POST /end` · `GET /help /health`.
No `/send_text` speak route. No audio, SDP, bearer, cookies ever cross it.

**Agent gateway (the adapter endpoint).** `POST /agent {text} → {reply}`, loopback-only,
no wildcard CORS, bounded body, per-call timeout; optional `GPTLIVE_TOKEN` header gate.

**MCP surface (Python, control-only).** `voice_live_status`, `voice_live_get_transcript`,
`voice_live_end`, `voice_live_export_help`. **No `voice_live_send_text`** (write channel cut).

## Acceptance oracle

1. Feeding a real `chat_message_delta` (`direction:"in"`) stream to `BridgeLayer.ingest`
   yields the exact human utterance; `direction:"out"` (Live's own speech) is NOT
   emitted as a human turn. (unit test, no browser/mic/LLM)
2. `isActionable` drops acks; a real question triggers exactly one `onUserSaid`.
3. Control plane exposes status/transcript/end only; there is no route that claims to
   make Live speak, and no API returns `delivered:true` for a Live-injection.
4. `POST /end` returns and tears down without deadlock.
5. Agent gateway rejects a missing token when `GPTLIVE_TOKEN` is set; bounds body size;
   times out a hung agent.
6. Reliable path documented = real Chrome + extension + gateway. Fake-mic sidecar is
   labelled test-only. Version metadata = 0.0.14 across pyproject/init/server.json.
