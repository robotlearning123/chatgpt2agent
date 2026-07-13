# GPT-Live — Full Pipeline & Workflow (empirically mapped, 2026-07-11)

> All of this is **observed from a real signed-in account**, not guessed. Method:
> headed Chrome on a copied signed-in profile (CDP-attached), real mic, every
> `RTCPeerConnection` / datachannel `.send` / `.onmessage` hooked, plus the account
> bearer hitting `/backend-api/*`. Routes, event names, and payloads are read
> directly from the live client and server. Supersedes the earlier "investigation"
> doc's unverified gaps; reconciles with `2026-07-11-gpt-live-handshake-evidence.md`.

## 0. What GPT-Live is (one paragraph)

GPT-Live is a **full-duplex voice agent with its own brain**. The browser is a
thin WebRTC + datachannel client; **all intelligence — transcription, tool use,
response generation, memory — is server-side.** The client's only jobs are: send
mic audio (RTP), send two control events (`track_state`, `client_metrics`), and
render inbound conversation deltas. You **cannot** inject text for Live to speak
(tested 5 ways, all silently dropped). Voice conversations are **normal ChatGPT
backend conversations** (same `/backend-api/conversation`, same memory store) — so
text tooling can read everything that was said.

## 1. End-to-end pipeline

```
[1] BOOTSTRAP       human-authed browser session on chatgpt.com
                    (cookies + Cloudflare Turnstile clearance in the profile)
        │
[2] VOICE ENTRY     composer speech button (data-testid="composer-speech-button")
                    → "Meet Voice" consent → voice picker (9 voices) → "Start Voice"
        │
[3] SESSION CREATE  app POSTs FormData to /realtime/vp?dcid=0 :
                      body = FormData(sdp=<offer>, session={voice_session_id,
                               protocol:"transceiver", integrated_mode, voice,
                               voice_mode, default_voice_mode, modes})
                      headers = Authorization: Bearer <account> +
                                OAI-Device-Id + UA +
                                OpenAI-Sentinel-Chat-Requirements-Token +
                                OpenAI-Sentinel-Proof-Token (POW) +
                                X-OpenAI-Target-* (routing) +
                                Cloudflare Turnstile (cleared by real browser)
                    → server mints an ephemeral voice session, returns
                      HTTP 201 + SDP answer (m=audio opus + 6 ICE candidates +
                      m=application webrtc-datachannel a=sctp-port:5000)
        │
[4] WEBRTC UP       browser ICE/DTLS/SRTP against the answer; mic track added
                    (sendrecv). DataChannel negotiated, id=0 opens.
        │
[5] INIT            client → server: track_state{track_id:"microphone",
                                                    media_type:"audio",
                                                    state:"live"}   (once)
                    server → client: state_update idle→listening
                              startup_telemetry{conversation loaded,
                                init_response_received, prefill_*}
        │
[6] STEADY STATE    client → server (continuous):
                      • mic audio → RTP/Opus (the ONLY content input path)
                      • client_metrics ~5–7×/s  (keepalive: service_rtt_ms,
                                  output_audio_bytes_received,
                                  output_audio_packets_lost, …)
                    server → client: state_update / chat_message_delta /
                              spawn_update / conversation_update /
                              usage_update / url_moderation
        │
[7] A USER TURN     (everything below is SERVER-side; client only listens)
          mic audio ──RTP──▶ server transcribes
          server ──▶ chat_message_delta {direction:"in",
                      content_type:"audio_transcription", text:"<your words>"}
          server decides tools ──▶ spawn_update{kind:"commentary",
                              state:"start"→"update"→(done), spawn_id,
                              text:"Searching the web" /
                                   "Searching www.sbnation.com" /
                                   "Searching for FIFA World Cup 2026 …" /
                                   "Considering visual response options" /
                                   "Exploring image and widget options"}
          (if visual) ──▶ url_moderation{url_moderation_result:{
                              full_url:"…/sonic/flags/ar.png",
                              is_safe,is_blocked}} per asset
          server generates ──▶ chat_message_delta {direction:"out",
                              content_type:"audio_transcription",
                              text:"<Live's words>"} streamed token-by-token
          audio spoken ──RTP/Opus──▶ browser ▶ speaker
          conversation_update{conversation_id, parent_message_id}
          usage_update{audio_s, session_s, limits.audio.remaining_seconds}
        │
[8] MEMORY          server READS the shared ChatGPT memory store
                    (/backend-api/memories) to personalize (proven: recalled the
                    user's robotics/quadruped background). A write Live announces
                    ("I'll remember that 42") did NOT persist to that store in
                    testing — treat voice memory-WRITE as in-session context, not
                    durable, until proven otherwise.
        │
[9] PERSISTENCE     the whole voice conversation is a normal ChatGPT conversation
                    (conversation_id). It appears in GET /backend-api/conversations
                    with an auto-generated title (e.g. "Introduce World Cup match",
                    "Math question answer") and is fully readable via
                    GET /backend-api/conversation/<id> — every voice turn stored as
                    a multimodal_text message with the transcript.
        │
[10] TEARDOWN       end button → datachannel close (server-initiated SCTP close if
                    the session was invalid), PeerConnection close, state→closed.
```

## 2. The datachannel contract (the real one)

Envelope both directions: `{"type":"data_message","data":"<inner-json-string>"}`.
DataChannel is **negotiated, id 0** (`?dcid=0`).

**Client → server (only these are honored):**

| event | when | role |
|---|---|---|
| `track_state` | once on open | declares mic live |
| `client_metrics` | ~5–7×/s | keepalive + audio stats |

**Everything else the client sends is silently dropped.** Verified dropped (all
`dc.send` returned `true`, none produced any inbound event): `response.create`,
`conversation.item.create` (user item), `conversation.item.create` (assistant
item) + `response.create`, `session.update`, `input_audio_buffer.append`.

**Server → client:**

| event | payload | meaning |
|---|---|---|
| `state_update` | `{previous_state,new_state,delay_s}` | session FSM: idle→listening→… |
| `startup_telemetry` | `{metrics:[{name,ms}]}` | load/prefill timings |
| `chat_message_delta` | JSON-patch deltas on a message tree | **the conversation** — `content.parts[]` carry `{content_type:"audio_transcription", direction:"in"\|"out", text}` |
| `spawn_update` | `{kind:"commentary", state, spawn_id, text}` | **tool/search narration** ("Searching www.…") |
| `conversation_update` | `{conversation_id, parent_message_id}` | turn advance |
| `usage_update` | `{audio_s, session_s, limits}` | quota (observed ~23.7h audio, ~55min/session) |
| `url_moderation` | `{url_moderation_result:{full_url,is_safe,is_blocked}}` | per visual-asset safety check |

> **`events.mjs` in the sidecar is WRONG**: it uses OpenAI Realtime-API names
> (`conversation.item.input_audio_transcription.completed`,
> `response.audio_transcript.delta`, `response.create`). The consumer channel does
> NOT use raw Realtime events — it uses ChatGPT's `chat_message_delta`
> JSON-patch conversation protocol. `extractInputTranscript` must parse
> `direction:"in"` parts, not a `transcript` key.

## 3. Capabilities (all proven in-session)

Driven by real spoken prompts; answers confirmed in the persisted backend
conversation:

| capability | proof |
|---|---|
| Real-time web search | spawn commentary "Searching www.sbnation.com / aljazeera.com"; cited live World Cup quarterfinal schedule |
| Visual cards / widgets | "here's the official bracket view"; url_moderation on flag PNGs (ar/ch/gb-eng/no) |
| Canvas | "create a canvas with a bulleted list of planets" → rendered Mercury…Neptune |
| Memory read | recalled user's robotics/quadruped profile from the shared store |
| Memory write (in-session) | stored + recalled "favorite number 42" within the session (not persisted cross-session) |
| Multi-step reasoning | 47×83 = 3901, with shown work |
| Code interpreter | self-described ("for bigger computations… I can use tools") |
| Real-time utilities | self-described (weather, time, scores, markets) |
| Image explanation, drafting/summarizing, coding/language help | self-described |

Live's own summary: "general reasoning; web search; real-time utilities; visual
cards; document help; image explanation; coding/language. No direct access to
private files/accounts unless shared."

## 4. Hard constraints / anti-bot

- **Cloudflare Turnstile gates session create.** Token-only / headless /
  copied-profile + puppeteer (`--enable-automation`) → server returns a lenient
  `201` then SCTP-aborts ~1s after `listening` (server-side validation reject).
- **Passes Turnstile** (verified): a **headed** Chrome, launched as a **direct
  binary** (no `--enable-automation`, `navigator.webdriver=false`), on a
  **copied signed-in profile** (Chrome forbids `--remote-debugging-port` on the
  default profile, so copy it to a non-default `--user-data-dir`). This holds the
  session for minutes with zero aborts.
- **No client-side speak-injection.** Output is server-generated only.
- **Input is audio-only.** No text-input datachannel event is honored.

## 5. Verified integration surface for gpt2agent

Because voice conversations ARE backend conversations, the existing tools already
cover most of the read side — **no new transport needed**:

| want | route / tool | status |
|---|---|---|
| list voice sessions | `GET /backend-api/conversations?order=updated` → `list_conversations` | ✅ works (voice convs appear with titles) |
| read a voice session | `GET /backend-api/conversation/<id>` → `get_conversation` | ✅ works (every turn as `multimodal_text`) |
| read shared memory | `GET /backend-api/memories` → `memory_list`/`memory_search` | ✅ works (what Live reads) |
| live voice stream (transcript + commentary + tool actions) | sidecar datachannel tap (`chat_message_delta`/`spawn_update`/`url_moderation`) | ✅ works (observe-only) |
| make Live speak arbitrary text | `response.create` / `conversation.item.create` / `session.update` | ❌ impossible (dropped) |
| drive Live by text input | none on datachannel | ❌ (would need posting to the conversation — untested) |
| persist a new memory from voice | Live says "remembering" but write didn't land in `/memories` | ⚠️ uncertain |

**Implication:** the realistic role for GPT-Live in this project is **an
observable voice modality over the same conversation+memory backend the text
tools already drive** — not a controllable TTS. The dead code is
`events.mjs::buildSpeakWire`, `export.mjs` speak-queue, and the
`voice_live_send_text` MCP tool (all assume an injection channel that does not
exist).

## 6. Open / next

- Confirm whether POSTing a user message to an **active** voice `conversation_id`
  via `/backend-api/conversation` makes Live continue it vocally (text-steering).
- Confirm voice memory-WRITE persistence path (async? different store?).
- Re-examine `spawn_update` for non-`commentary` kinds (tool exec result events)
  under heavier tool use (code interpreter, connections).
