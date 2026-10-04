from __future__ import annotations

import re
from typing import Any

from gpt2agent.backend import BackendClient
from gpt2agent.tools._backend import async_get

#: OpenAI "dots" (always-on GPT-6 Astra agents, launched 2026-09-29) expose no
#: documented API. Detection therefore keys on structural markers observed in
#: account reads: dot-named fields anywhere in a payload, or a conversation
#: ``conversation_origin`` naming dots. Catalog slugs alone never count — the
#: ``gpt-6-astra-wm`` entry ships to accounts without dots (verified
#: 2026-10-04: it routes to gpt-5-6 like the other ``-wm`` slugs).
_DOT_KEY_RE = re.compile(r"(?<![A-Za-z])dots?(?![A-Za-z])", re.IGNORECASE)

#: Origin types already claimed by non-dot features; anything else is reported
#: as an unknown candidate for visibility, not as a dot.
_KNOWN_ORIGIN_TYPES = {"custom_gpt"}


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


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    async def dots_status() -> dict:
        """Report whether OpenAI dots (always-on agents) are usable on this account.

        Dots have no documented API and roll out gradually to Pro plans; this
        tool reads only documented GET surfaces (conversations, model catalog,
        account check) and reports the structural markers. Returns a dict with:
        `dots_detected` (bool), `status` ("detected" or "not_rolled_out"),
        `checked_conversations`, `automation_conversation_ids` (conversations
        flagged `is_automation_conversation` — dot candidates), `dot_named_fields`
        (any dot-named keys found in the payloads), `astra_catalog_slugs`
        (GPT-6 Astra catalog entries — context only, NOT dots access), and
        `unknown_conversation_origins`. When `dots_detected` is false, dots
        cannot be driven from this server yet; see docs/dots.md for the
        unlock runbook.
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

        detected = bool(dot_fields) or any("dot" in o.lower() for o in unknown_origins)
        return {
            "dots_detected": detected,
            "status": "detected" if detected else "not_rolled_out",
            "checked_conversations": len(items) if isinstance(items, list) else 0,
            "automation_conversation_ids": automation_ids,
            "dot_named_fields": dot_fields,
            "astra_catalog_slugs": astra_slugs,
            "unknown_conversation_origins": sorted(set(unknown_origins)),
        }
