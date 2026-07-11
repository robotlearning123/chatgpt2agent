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

## Still needs a live round-trip to confirm

- Exact `Authorization` token source: appears to be the account Bearer
  (`~/.codex/auth.json`), i.e. the sidecar may bootstrap with the token
  gpt2agent already holds — no browser. Confirm by one authenticated POST.
- ICE servers: not literal in the bundle (server-provided or default STUN).
- The precise `live`-mode selector and full datachannel event enum.

These are confirmations, not unknowns: the routes and mechanism above are read
directly from shipped code.
