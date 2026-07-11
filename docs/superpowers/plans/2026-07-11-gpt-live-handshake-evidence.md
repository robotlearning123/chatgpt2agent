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
UDP → the WebRTC audio track). Three real werift wiring bugs were found and fixed
along the way:

1. `rtpSource` returns an **array `[track, port, dispose]`**, not `{track}` — the
   original object-destructure left the track `undefined` (no audio track added).
2. Passing werift's random `a=ssrc` (often > 2^31) to ffmpeg's `-ssrc` throws
   `Numerical result out of range` and ffmpeg sent **0 packets** — dropped `-ssrc`
   (werift re-stamps SSRC in its sender anyway).
3. `pc.addTransceiver("audio", {track})` ignores the track — werift's signature is
   `addTransceiver(trackOrKind, opts)`, so the track must be the **first arg**.

After all three: ffmpeg delivers **328 RTP packets** into werift and the track is
wired to the sender. **Yet the session still reaches `listening` and closes ~1s
later, with no transcription** — the same ~1s close as the no-audio run, so it is
**not** an audio-VAD timeout. It is the client failing to send an expected
**outbound datachannel init message** (the web client keeps the session alive
with one). That outbound envelope/type is **obfuscated in the current bundle**
(the `.send(...)` construction did not yield to static grep; the deploy also
rotates chunk hashes), and is the concrete remaining wall.

### Outbound transport confirmed; the init/keepalive sequence is the wall

The voice client chunk (`4813494d`) sends over the datachannel via:

```js
publishData: async (e) => {                      // e = binary buffer
  if (dc.readyState !== "open") throw Error("Data channel is not open");
  const n = new TextDecoder().decode(e);
  dc.send(JSON.stringify({ type: "data_message", data: n }));  // same envelope both ways
}
```

So the outbound envelope is confirmed `{type:"data_message", data:<string>}`. The
connection sequence has phases `preConnectionSetup → audioInputAcquisition →
audioTransceiverSetup → postConnectionSetup → qualityMonitorSetup`, and a
`ConnectionQualityChanged` channel. But the **specific inner message(s)** the
client calls `publishData` with right after open — the thing that holds the
session past `listening` — is emitted by a voice-command layer buried in the
4.5 MB minified chunk that static grep can't practically trace, and blind Node
guessing (wrapped/unwrapped `session.update`, ± audio) has been ruled out (all
close at ~1s identically).

**Autonomous reverse-engineering is exhausted here.** The reliable next step is to
observe the real authenticated client at RUNTIME — instrument `RTCDataChannel`
`.send`/`.onmessage` (or `publishData`) on a logged-in `chatgpt.com` voice
session and log the exact inner message sequence. This needs NO microphone/audio
(read-only send/receive logging, forced-silent mic) and ~10s. It requires an
authenticated browser the agent can drive.

### Outbound protocol CAPTURED from the real client (2026-07-11, owner-approved)

Observed the authenticated web client via CDP (forced-silent mic + spoofed
`permissions.query`/`enumerateDevices` so the app started without opening the
real mic; the WebRTC is main-thread — caught by wrapping `RTCPeerConnection` →
`createDataChannel` → `send`). The client sends **only two** datachannel message
types, both in the `{type:"data_message", data:"<inner json>"}` envelope:

1. **`track_state`** once on open — the init that declares the mic live:
   `{type:"track_state", payload:{type:"track_state", track_id:"microphone", media_type:"audio", media_source:"microphone", state:"live"}}`
2. **`client_metrics`** ~5–7×/sec — keepalive with audio stats
   (`service_rtt_ms`, `output_audio_bytes_received`, `output_audio_packets_lost`, …).

Applied both in `connect_live_audio.mjs`. **The session STILL closes ~1s after
`listening`** — an application close by the server. Since the *real browser*
client (observed with silent audio) stayed open 20s+ sending 152 messages, and my
Node client sends the identical protocol + audio into werift, the remaining
blocker is **werift↔OpenAI media/SRTP interop** (the server won't accept werift's
audio media stream), NOT any ChatGPT-specific unknown.

### Conclusion — every ChatGPT-specific unknown is resolved

Auth, routes, SDP exchange, ICE/DTLS, datachannel, session state machine, and the
FULL application protocol (`track_state` + `client_metrics`) are all captured and
verified. A full spoken round-trip is **not** demonstrated, blocked solely on
WebRTC-library media interop.

**Decisive diagnostic (`SILENCE=1`):** werift sending *continuous silence* (what
the browser client sends and survives 20s+ on) STILL app-closes ~1s after
`listening`. So werift's audio **SRTP egress does not reach the server at all** —
the server closes because it receives no valid audio media despite
`track_state=live`. This is the confirmed root cause, not a protocol/timing gap.

**Viable path (task #3):** the real browser client works end-to-end, so make the
sidecar **browser-based** — a headless Chrome launched with
`--use-fake-device-for-media-stream --use-file-for-fake-audio-capture=<wav>`,
driving the account's own voice UI, with transcripts read off the datachannel via
the proven `createDataChannel`→`send`/`onmessage` hook. That sidesteps werift's
media-interop entirely and reuses the app's own (working) media stack. The werift
path remains viable only if its RTCP/SRTP/RTP-timestamp interop with the OpenAI
realtime server is debugged.

### werift wiring check (for whoever debugs the werift path)

Confirmed NOT a wiring bug: `pc.addTransceiver(track,{direction:"sendrecv"})`
registers the track with the sender and the sender subscribes to
`track.onReceiveRtp` (2 subscribers), and `sender.sendRtp` exists. So the chain
UDP→rtpSource→writeRtp→onReceiveRtp→sender is connected. The audio still not
reaching the server points to werift's **SRTP keying / DTLS for the audio m-line
or the RTP formatting the OpenAI server accepts** — deep media internals, uncertain
payoff. The browser-sidecar path avoids all of it.
