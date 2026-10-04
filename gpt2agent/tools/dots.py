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


def _dot_named_fields(obj: Any, path: str = "$", hits: list[str] | None = None) -> list[str]:
    """Paths of every dict key whose name is the word ``dot``/``dots``."""
    hits = hits if hits is not None else []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if isinstance(k, str) and _DOT_KEY_RE.search(k):
                hits.append(p)
            _dot_named_fields(v, p, hits)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:100]):
            _dot_named_fields(v, f"{path}[{i}]", hits)
    return hits


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
        convs = await async_get(
            client,
            "/backend-api/conversations?limit=50",
            target_path="/backend-api/conversations",
        ) or {}
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

        models = await async_get(
            client,
            "/backend-api/models?history_and_training_disabled=false",
            target_path="/backend-api/models",
        ) or {}
        astra_slugs = sorted(
            {
                str(m.get("slug"))
                for m in (models.get("models") or [])
                if isinstance(m, dict) and "astra" in str(m.get("slug") or "").lower()
            }
        )

        check = await async_get(
            client,
            "/backend-api/accounts/check/v4-2023-04-27",
            target_path="/backend-api/accounts/check/v4-2023-04-27",
        ) or {}
        dot_fields += _dot_named_fields(check, path="accounts_check")

        autos = await async_get(client, _AUTOMATIONS_PATH, target_path=_AUTOMATIONS_PATH) or {}
        auto_items = autos.get("items") or []
        cloud_autos = [a for a in auto_items if isinstance(a, dict) and a.get("executor") == "cloud"]
        aeon_count = sum(1 for a in cloud_autos if a.get("aeon_id"))

        detected = bool(dot_fields) or any("dot" in o.lower() for o in unknown_origins)
        return {
            "dots_detected": detected,
            "status": "detected" if detected else "not_rolled_out",
            "checked_conversations": len(items) if isinstance(items, list) else 0,
            "automation_conversation_ids": automation_ids,
            "dot_named_fields": dot_fields,
            "astra_catalog_slugs": astra_slugs,
            "unknown_conversation_origins": sorted(set(unknown_origins)),
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
        rule = rrule or f"FREQ={frequency.upper()};BYHOUR={by_hour};BYMINUTE={by_minute}"
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
