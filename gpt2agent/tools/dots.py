from __future__ import annotations

import re
from datetime import datetime, timezone as dt_timezone
from typing import Any

from gpt2agent.backend import BackendClient
from gpt2agent.tools._backend import async_get, async_post
from gpt2agent.tools._redact import redact

#: OpenAI "dots" (always-on GPT-6 Astra agents, launched 2026-09-29) expose no
#: documented API. Detection therefore keys on structural markers observed in
#: account reads: dot-named fields anywhere in a payload, or a conversation
#: ``conversation_origin`` naming dots. Catalog slugs alone never count — the
#: ``gpt-6-astra-wm`` entry ships to accounts without dots (verified
#: 2026-10-04: it routes to gpt-5-6 like the other ``-wm`` slugs).
_DOT_KEY_RE = re.compile(r"(?<![A-Za-z])dots?(?![A-Za-z])", re.IGNORECASE)

#: Origin types already claimed by non-dot features; anything else is reported
#: as an unknown candidate for visibility, not as a dot.
_KNOWN_ORIGIN_TYPES = {"custom_gpt", "tpp"}

_AUTOMATIONS_PATH = "/backend-api/automations"

_PROMPT_CAP = 280


async def _safe_get(client: BackendClient, path: str, target: str,
                    errors: list[str], label: str):
    """GET that degrades instead of killing the whole status report; the
    failure is surfaced in `errors` (found by completeness critic 2026-10-04)."""
    try:
        return await async_get(client, path, target_path=target)
    except Exception as e:  # noqa: BLE001
        errors.append(f"{label}: {str(e).splitlines()[0][:120]}")
        return None


async def _default_dot_room(client: BackendClient) -> str | None:
    """First messaging room tied to an aeon (the dot DM). Single source for
    dot_messages/send_to_dot default resolution."""
    rooms = await async_get(client, "/backend-api/messaging/rooms?limit=10",
                            target_path="/backend-api/messaging/rooms") or {}
    for r in rooms.get("items") or []:
        if isinstance(r, dict) and r.get("aeon_id") and r.get("id"):
            return str(r["id"])
    return None


def _dot_named_fields(obj: Any, path: str = "$", hits: list[str] | None = None) -> list[tuple[str, Any]]:
    """(path, value) of every dict key whose name is the word ``dot``/``dots``."""
    hits = hits if hits is not None else []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if isinstance(k, str) and _DOT_KEY_RE.search(k):
                hits.append((p, v))
            _dot_named_fields(v, p, hits)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:100]):
            _dot_named_fields(v, f"{path}[{i}]", hits)
    return hits


_FREQUENCIES = ("daily", "weekly", "hourly", "minutely")


def _rrule_for(frequency: str, by_hour: int, by_minute: int) -> str:
    """RRULE body per frequency — BYHOUR is a *filter*, so it must only be
    applied where it means "at this time each day" (daily/weekly). Appending
    it to HOURLY/MINUTELY would collapse recurrence to once a day at that
    hour. Unknown values raise instead of silently falling back to DAILY
    (a typo must not create a 30x-more-frequent job — found by independent
    review 2026-10-04)."""
    f = (frequency or "").strip().lower()
    if f not in _FREQUENCIES:
        raise ValueError(
            f"frequency must be one of {', '.join(_FREQUENCIES)} (or pass a raw rrule=); got {frequency!r}"
        )
    if f == "minutely":
        return "FREQ=MINUTELY"
    if f == "hourly":
        return f"FREQ=HOURLY;BYMINUTE={by_minute}"
    if f == "weekly":
        return f"FREQ=WEEKLY;BYHOUR={by_hour};BYMINUTE={by_minute}"
    return f"FREQ=DAILY;BYHOUR={by_hour};BYMINUTE={by_minute}"


def _vevent(rrule: str, dtstart: str) -> str:
    """Wrap an RRULE in the VEVENT string the automations API expects.

    Wire shape verified by execution 2026-10-04: ``schedule`` must be the full
    ``BEGIN:VEVENT\\nDTSTART:...\\nRRULE:...\\nEND:VEVENT`` string (a dict is a
    422 "string_type"; a bare RRULE is not what the desktop app sends).
    """
    return f"BEGIN:VEVENT\nDTSTART:{dtstart}\nRRULE:{rrule}\nEND:VEVENT"


def _today_utc() -> str:
    return datetime.now(dt_timezone.utc).strftime("%Y%m%dT000000Z")


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    async def dots_status() -> dict:
        """Report whether OpenAI dots (always-on agents) are usable on this account.

        Dots have no documented API and roll out gradually to Pro plans; this
        tool reads only documented GET surfaces (conversations, model catalog,
        account check, automations) and reports the structural markers.
        Returns a dict with: `dots_detected` (bool), `status` ("detected" or
        "not_rolled_out"), `checked_conversations`, `automation_conversation_ids`
        (conversations flagged `is_automation_conversation` — dot candidates),
        `dot_named_fields` (any dot-named keys found in the payloads),
        `astra_catalog_slugs` (GPT-6 Astra catalog entries — context only,
        NOT dots access), `unknown_conversation_origins`, and `automations`
        (cloud/aeon counts: dot-driven scheduled work rides the automations
        API — see `list_automations`). When `dots_detected` is false, direct
        dot messaging is not available; scheduled dot work is still
        controllable via the automation tools. See docs/dots.md.
        """
        errors: list[str] = []
        convs = await _safe_get(client, "/backend-api/conversations?limit=50",
                                "/backend-api/conversations", errors, "conversations") or {}
        items = convs.get("items") or []
        automation_ids: list[str] = []
        dot_fields: list[str] = []
        unknown_origins: list[str] = []
        for it in items if isinstance(items, list) else []:
            if not isinstance(it, dict):
                continue
            if it.get("is_automation_conversation") is True:
                automation_ids.append(str(it.get("id")))
            dot_fields += _dot_named_fields(it, path=f"conv[{it.get('id')}]")
            origin = it.get("conversation_origin")
            otype = origin.get("type") if isinstance(origin, dict) else None
            if isinstance(otype, str) and otype and otype not in _KNOWN_ORIGIN_TYPES:
                unknown_origins.append(otype)

        models = await _safe_get(client, "/backend-api/models?history_and_training_disabled=false",
                                 "/backend-api/models", errors, "models") or {}
        astra_slugs = sorted(
            {
                str(m.get("slug"))
                for m in (models.get("models") or [])
                if isinstance(m, dict) and "astra" in str(m.get("slug") or "").lower()
            }
        )

        check = await _safe_get(client, "/backend-api/accounts/check/v4-2023-04-27",
                                "/backend-api/accounts/check/v4-2023-04-27", errors, "accounts_check") or {}
        dot_fields += _dot_named_fields(check, path="accounts_check")

        autos = await _safe_get(client, _AUTOMATIONS_PATH, _AUTOMATIONS_PATH, errors, "automations") or {}
        auto_items = autos.get("items") or []
        cloud_autos = [a for a in auto_items if isinstance(a, dict) and a.get("executor") == "cloud"]
        aeon_count = sum(1 for a in cloud_autos if a.get("aeon_id"))

        # A dot-named key claims detection only when its scalar value is not
        # an explicit off (False/None/0) — e.g. {"dots_enabled": false} must
        # not read as available (found by independent review 2026-10-04).
        hard_marker = any(
            (not isinstance(v, (dict, list)) and v not in (False, None, 0, "", "disabled", "false"))
            or (isinstance(v, (dict, list)) and v)
            for _, v in dot_fields
        )
        detected = hard_marker or any("dot" in o.lower() for o in unknown_origins)
        hint = (
            "Dots detected — use list_dots / dot_messages / the automation tools."
            if detected else
            "No dot markers yet. If you have not created a dot: create one in the "
            "ChatGPT desktop app or desktop web (Pro plan; rollout is gradual), then "
            "retry. The automation tools may still work regardless. Details: docs/dots.md"
        )
        return {
            "dots_detected": detected,
            "status": "detected" if detected else "not_rolled_out",
            "hint": hint,
            "checked_conversations": len(items) if isinstance(items, list) else 0,
            "automation_conversation_ids": automation_ids,
            "dot_named_fields": [p for p, _ in dot_fields],
            "astra_catalog_slugs": astra_slugs,
            "unknown_conversation_origins": sorted(set(unknown_origins)),
            "errors": errors,
            "automations": {
                "total": len(auto_items),
                "cloud_executor": len(cloud_autos),
                "with_aeon_id": aeon_count,
                "note": "cloud-executor automations run in the dot runtime; "
                        "controllable via list/create/set_automation_status/remove_automation",
            },
        }

    @mcp.tool()
    async def list_automations(limit: int = 20) -> list[dict]:
        """List scheduled automations (the dot's recurring work surface).

        Returns a list of dicts with: `id`, `title` (PII-redacted),
        `prompt` (PII-redacted, truncated), `is_enabled`, `executor`
        ("cloud" = dot runtime), `timing_mode`, `schedule` (RRULE excerpt),
        `last_run_time`, `next_run_times` (first 3), `display_emoji`,
        `can_delete`. The write tools address automations by this `id`.
        """
        data = await async_get(client, _AUTOMATIONS_PATH, target_path=_AUTOMATIONS_PATH) or {}
        items = data.get("items") or []
        out: list[dict] = []
        for it in items[: max(0, limit)] if isinstance(items, list) else []:
            if not isinstance(it, dict):
                continue
            prompt = redact(str(it.get("prompt") or ""))
            out.append({
                "id": it.get("id"),
                "title": redact(str(it.get("title") or "")),
                "prompt": prompt[:_PROMPT_CAP] + ("…" if len(prompt) > _PROMPT_CAP else ""),
                "is_enabled": bool(it.get("is_enabled")),
                "executor": it.get("executor"),
                "timing_mode": it.get("timing_mode"),
                "schedule": " ".join(str(it.get("schedule") or "").split("\n"))[:120],
                "last_run_time": it.get("last_run_time"),
                "next_run_times": (it.get("next_run_times") or [])[:3],
                "display_emoji": it.get("display_emoji"),
                "can_delete": bool(it.get("can_delete")),
            })
        return out

    @mcp.tool()
    async def create_automation(
        prompt: str,
        title: str | None = None,
        frequency: str = "daily",
        by_hour: int = 3,
        by_minute: int = 0,
        rrule: str | None = None,
        timezone: str | None = None,
        executor: str = "cloud",
        enabled: bool = False,
        model: str | None = None,
        reasoning_effort: str | None = None,
    ) -> dict:
        """Create a scheduled automation (dot recurring work). Defaults to DISABLED.

        `frequency` is one of daily/weekly/hourly/minutely (composed with
        `by_hour`/`by_minute`), or pass a raw `rrule` (e.g.
        "FREQ=WEEKLY;BYDAY=MO,FR;BYHOUR=9;BYMINUTE=30"). `executor="cloud"`
        runs in the dot runtime; `enabled` defaults to False — the automation
        is created paused and only runs after `set_automation_status` (or the
        ChatGPT UI) enables it. Returns the created automation dict (with
        `id`). Wire shape verified by execution 2026-10-04 (title required,
        schedule = full VEVENT string, timing_mode = 0 for exact schedules).
        """
        rule = rrule or _rrule_for(frequency, by_hour, by_minute)
        payload: dict[str, Any] = {
            "title": title or prompt[:60],
            "prompt": prompt,
            "schedule": _vevent(rule, _today_utc()),
            "timing_mode": 0,
            "default_timezone": timezone or "UTC",
            "executor": executor,
            "is_enabled": enabled,
            "jawbone_id": None,
            "legacy_automation_id": None,
            "notification_policy": None,
            "notifications_enabled": False,
            "email_enabled": False,
            "target_thread_id": None,
        }
        if model:
            payload["model"] = model
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        return await async_post(client, "/backend-api/automations/save", json=payload,
                                target_path="/backend-api/automations/save") or {}

    @mcp.tool()
    async def set_automation_status(automation_id: str, enabled: bool) -> dict:
        """Enable or disable a scheduled automation (id from `list_automations`)."""
        return await async_post(
            client,
            "/backend-api/automations/set_status",
            json={"jawbone_id": automation_id, "is_enabled": enabled},
            target_path="/backend-api/automations/set_status",
        ) or {}

    @mcp.tool()
    async def remove_automation(automation_id: str) -> dict:
        """Delete a scheduled automation (id from `list_automations`)."""
        return await async_post(
            client,
            "/backend-api/automations/remove",
            json={"automation_id": automation_id},
            target_path="/backend-api/automations/remove",
        ) or {}

    @mcp.tool()
    async def list_dots(limit: int = 10) -> list[dict]:
        """List the account's dots (always-on agents) with their DM rooms.

        Returns a list of dicts with: `aeon_id` (the dot instance id, also
        the automation runtime id), `display_name`, `room_id`, `room_name`,
        `room_updated_at`. Reads two GET surfaces: the aeon registry
        (`/backend-api/tbo`) and the messaging rooms list. Messages are read
        with `dot_messages`; scheduled work with `list_automations`.
        """
        tbos = await async_get(client, "/backend-api/tbo?limit=25",
                               target_path="/backend-api/tbo") or {}
        rooms = await async_get(client, f"/backend-api/messaging/rooms?limit={max(1, limit)}",
                                target_path="/backend-api/messaging/rooms") or {}
        room_by_aeon = {
            r.get("aeon_id"): r
            for r in (rooms.get("items") or []) if isinstance(r, dict) and r.get("aeon_id")
        }
        out: list[dict] = []
        for t in (tbos.get("items") or [])[: max(0, limit)]:
            if not isinstance(t, dict):
                continue
            aeon = t.get("id")
            room = room_by_aeon.get(aeon) or {}
            out.append({
                "aeon_id": aeon,
                "display_name": t.get("display_name") or "",
                "room_id": room.get("id"),
                "room_name": room.get("name"),
                "room_updated_at": room.get("updated_at"),
            })
        return out

    @mcp.tool()
    async def dot_messages(limit: int = 20, room_id: str | None = None) -> list[dict] | dict:
        """Read the dot conversation (newest last).

        `room_id` comes from `list_dots`; when omitted, the first room with an
        `aeon_id` is used (the account's dot DM). Returns a list of dicts
        with: `role` ("DOT" or "OWNER"), `created_at`, `text` (PII-redacted,
        truncated to 400 chars). The upstream page cap is 32 messages. When
        the account has no dot yet, returns a friendly dict instead:
        `{"status": "no_dot", "dots_available": false, "how_to_enable": ...}`.
        Sending is deliberately NOT offered: REST posts persist but do not
        wake the dot (the wake rides the desktop app's realtime channel) —
        see docs/dots.md.
        """
        if not room_id:
            room_id = await _default_dot_room(client)
        if not room_id:
            return {
                "status": "no_dot",
                "dots_available": False,
                "how_to_enable": "Create your dot in the ChatGPT desktop app or "
                                 "desktop web (Pro plan; rollout is gradual), then "
                                 "retry. See docs/dots.md.",
            }
        data = await async_get(
            client,
            f"/backend-api/messaging/rooms/{room_id}/messages?limit={min(max(1, limit), 32)}",
            target_path=f"/backend-api/messaging/rooms/{room_id}/messages",
        ) or {}
        items = data.get("items") or []
        msgs = [m for m in items if isinstance(m, dict)]
        msgs.sort(key=lambda m: str(m.get("created_at") or ""))
        out: list[dict] = []
        for m in msgs:
            text = redact(str((m.get("content") or {}).get("text") or ""))
            out.append({
                "role": "DOT" if str(m.get("account_user_id") or "").startswith("calpico-member-") else "OWNER",
                "created_at": m.get("created_at"),
                "text": text[:400] + ("…" if len(text) > 400 else ""),
            })
        return out

    @mcp.tool()
    async def send_to_dot(text: str, room_id: str | None = None) -> dict:
        """Send a message to your dot (async delivery; the dot replies later).

        `room_id` defaults to the dot DM from `list_dots`. The message is
        delivered into the dot's room and the dot processes it on its own
        cadence — observed latency ~16 minutes (n=1, 2026-10-04), versus
        ~6-10 s when typed in the desktop app (which rides the realtime
        channel). Poll `dot_messages` for the reply. Returns
        `{delivered, verified_in_room, room_id, note}` — delivery is judged
        by the message appearing in the room, NOT by the upstream HTTP code
        (upstream answers 422 "stable send identifier" even on successful
        persistence; that is expected). For instant turnaround, type in the
        ChatGPT desktop app instead.
        """
        if not room_id:
            room_id = await _default_dot_room(client)
        if not room_id:
            return {"delivered": False,
                    "how_to_enable": "Create your dot in the ChatGPT desktop app or "
                                     "desktop web (Pro plan), then retry. See docs/dots.md."}
        text = (text or "").strip()
        if not text:
            return {"delivered": False, "error": "text must be a non-empty string"}

        def _ids_and_owner_texts(data: dict) -> tuple[set, dict]:
            ids: set = set()
            owner_texts: dict = {}
            for m in data.get("items") or []:
                if not isinstance(m, dict) or not m.get("id"):
                    continue
                ids.add(m["id"])
                if not str(m.get("account_user_id") or "").startswith("calpico-member-"):
                    owner_texts[m["id"]] = str((m.get("content") or {}).get("text") or "")
            return ids, owner_texts

        # Readback is judged against ids present BEFORE the send, matching the
        # exact full text on an OWNER-authored NEW message — stale repeats,
        # DOT quotations, or shared prefixes cannot claim delivery
        # (found by independent review 2026-10-04).
        before = await async_get(
            client, f"/backend-api/messaging/rooms/{room_id}/messages?limit=8",
            target_path=f"/backend-api/messaging/rooms/{room_id}/messages") or {}
        prior_ids, _ = _ids_and_owner_texts(before)

        try:
            await async_post(client, f"/backend-api/messaging/rooms/{room_id}/messages",
                             json={"content": {"text": text}},
                             target_path=f"/backend-api/messaging/rooms/{room_id}/messages")
        except RuntimeError as e:
            # Expected upstream answer for API sends: HTTP 422 with the
            # stable-send-identifier detail, on successful persistence.
            # Anything else is a real failure and must surface.
            msg = str(e)
            if not ("422" in msg and "stable send identifier" in msg):
                raise

        after = await async_get(
            client, f"/backend-api/messaging/rooms/{room_id}/messages?limit=8",
            target_path=f"/backend-api/messaging/rooms/{room_id}/messages") or {}
        new_ids, owner_texts = _ids_and_owner_texts(after)
        seen = any(owner_texts.get(i) == text for i in new_ids - prior_ids)
        return {
            "delivered": seen,
            "verified_in_room": seen,
            "room_id": room_id,
            "note": "Dot processes API-sent messages on its own cadence "
                    "(observed ~16 min; app-typed messages get ~6-10 s turnaround). "
                    "Poll dot_messages for the reply.",
        }
