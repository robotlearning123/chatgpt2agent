# GPT-Live handshake — captured from the public web bundle (2026-07-11)

**Method:** No voice session, mic, or credentials. Fetched ChatGPT's public JS
from the CDN on the Linux host and grepped the realtime chunks. This closed the
gaps that the headless-browser capture could not (no audio device there).

**Provenance:** `https://chatgpt.com/cdn/assets/manifest-79556052.js` →
`routes/voice` → the realtime code lives in chunk
`9a292b8a-j6dq5kgt13mzsd7q.js` (plus `4813494d-…` and
`conversation-small-…`). Deploy-specific hashes; the *shapes* are what matter.

## Endpoint (verified)

Route builder from the bundle:

```js
voicePath(e){ let t=`/realtime`;
  return this.sessionType()===`wm` ? `${t}/wm`
    : `${t}/vp${e===`standard`?`s`:``}` }
// Usn = e => ({ baseUrl: Hsn(), path: voicePath(e) })   // Hsn() = window.location.origin
// Wsn: URLSearchParams set `dcid` (default 0)
```

So the WebRTC endpoint is:

| mode | URL |
|---|---|
| standard | `${origin}/realtime/vps?dcid=0` |
| advanced | `${origin}/realtime/vp?dcid=0` |
| wingman | `${origin}/realtime/wm?dcid=0` |
| status | `${origin}/realtime/status` |

`origin` = `https://chatgpt.com`. (Note: `voice_mode=live` is rejected by the
*catalog* route with 422 — Live is a session mode here, e.g. it maps through the
same `/realtime/vp` family; the exact `live` selector still needs a live check.)

## SDP exchange (verified, single-shot)

```js
pc.createOffer()
  .then(o => (pc.setLocalDescription(o),
     fetch(peerURL, { method:"POST", body:o.sdp,
        headers:{ "Content-Type":"application/sdp", ...additionalHeaders }})))  // additionalHeaders carries Authorization: Bearer <token>
  .then(r => r.text())
  .then(answerSdp => pc.setRemoteDescription({ type:"answer", sdp:answerSdp }));
```

This is the OpenAI Realtime WebRTC pattern on the chatgpt.com origin. No separate
"create session then exchange" two-step is needed for the core voice path: the
server mints the session from the authenticated SDP POST.

## Datachannel (verified)

```js
pc.createDataChannel("", { negotiated:true, id:0 })   // negotiated, id 0 (== ?dcid=0)
```

Event model is Realtime-API-style — observed fragments: `session.update`,
`response.audio_blocked`, `audio_transcription`, `output_audio_buffer_depth_ms`.
This confirms the two events Mode B needs exist in this family: an input
*transcription* event and `response.*` / `session.update` for driving output.

## Session fields (verified)

`voice_session_id`, `voice`, `voice_mode`, `default_voice_mode`, `modes`.

## Live round-trip — CONFIRMED (2026-07-11, account token, no browser)

Two authenticated `POST`s to `https://chatgpt.com/realtime/vp?dcid=0` using the
account bearer from `~/.codex/auth.json` (curl_cffi Chrome impersonation, the
same path gpt2agent uses). No mic, no browser, no ephemeral token, no sentinel.

1. A datachannel-only offer returned **`HTTP 400`**:
   `{"error":{"message":"Offer did not have an audio media section.","type":"invalid_request_error","code":"invalid_offer"}}`
   — auth passed, route correct, OpenAI Realtime error schema.
2. An offer with an Opus audio m-line + datachannel returned **`HTTP 201`** with a
   full **SDP answer** (39 lines): `m=audio … opus/48000/2`, `a=setup:active`,
   **6 `a=candidate:` ICE candidates**, and `m=application … webrtc-datachannel`
   `a=sctp-port:5000`.

**Resolved:**
- **Token source = the account bearer.** The sidecar bootstraps GPT-Live with the
  token gpt2agent already loads — **no browser at all**.
- **ICE servers** come embedded in the SDP answer (candidates), not from a
  separate config.
- Endpoint, `application/sdp` format, and negotiated datachannel are confirmed
  against the live server.

**Still open (media, not control plane):** completing ICE/DTLS/SRTP needs a real
WebRTC peer (Node `werift`/`wrtc`, or a browser) — the probe used bogus ICE creds
so media never connects and the half-open session expires server-side. The
`live`-mode selector and the full datachannel event enum are the last minor
items, observable once a real peer connects.

The SDP-exchange control plane — the thing that was blocked — is now verified
end-to-end. `src/adapter.mjs::exchangeSdp` is exactly this call.

## Full WebRTC connection — SUCCEEDED from Node (2026-07-11)

`sidecar/experiments/connect_live.mjs` (werift peer + `sdp_exchange.py` for the
POST) established a **real WebRTC session to live GPT-Live** — no browser, no mic:

```
[ice] checking -> completed -> connected
[sdp_exchange] HTTP 201
[conn] connecting -> connected            # ICE + DTLS complete
[dc] open                                 # negotiated datachannel id:0 open
[msg 1] state_update: idle -> listening   # server accepted the session
```

So ICE/DTLS/SCTP all interoperate with werift and the account token alone.

### Datachannel protocol (observed, consumer-specific — NOT raw Realtime API)

Inbound messages are wrapped in an envelope:

```json
{"type":"data_message","data":"{\"type\":\"state_update\",\"payload\":{\"type\":\"state_update\",\"previous_state\":\"idle\",\"new_state\":\"listening\",\"delay_s\":null}}"}
```

i.e. outer `data_message` → inner event (`state_update` with
`previous_state`/`new_state`). The session state machine begins `idle →
listening`, then closes within ~1s.

### Audio round-trip — attempted, not yet decoded server-side

`sidecar/experiments/connect_live_audio.mjs` sends a TTS utterance (`mb voice` →
mp3 → `ffmpeg -c:a libopus -f rtp` → werift `MediaStreamTrackFactory.rtpSource`
UDP → the WebRTC audio track). Verified aligned: audio starts on datachannel
open, Opus PT matches offer/answer (96/96), and ffmpeg SSRC matches werift's
declared `a=ssrc`. Result: the session still reaches `listening` and drops ~1s
later — **GPT-Live is not decoding the sent audio** (no transcription event
appears). The egress path (werift SRTP sender actually forwarding the
rtpSource-injected RTP with correct timestamps) is the open item; the fix likely
needs werift's canonical media-send path rather than raw RTP forwarding.

**So, verified end-to-end: auth, routes, SDP exchange, ICE/DTLS, datachannel,
and the session state machine. Open (task #3): server-side audio decode (getting
the human's Opus to actually reach GPT-Live's recognizer) and the outbound
command envelope, then the Mode B loop.**
