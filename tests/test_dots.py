"""Unit tests for the dots_status tool — no network.

Detection must be capable of a positive (a marker flips `dots_detected`) so
that a live "not_rolled_out" result carries power: these tests fake payloads
with and without dot markers and assert both directions. The negative-result
rule from the anti-hallucination standard is the reason this file exists.
"""

from __future__ import annotations

import asyncio
from typing import Any

from gpt2agent.tools import dots


class FakeMCP:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self, *a: Any, **k: Any):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn
        return deco


class FakeClient:
    def __init__(self, routes: dict | None = None) -> None:
        self.routes = routes or {}
        self.gets: list[str] = []

    def get(self, path: str, target_path: str | None = None, **k: Any) -> Any:
        self.gets.append(path)
        for pat, val in self.routes.items():
            if path == pat or path.startswith(pat):
                return val
        return {}


def _reg(routes: dict) -> tuple[FakeMCP, FakeClient]:
    client = FakeClient(routes)
    mcp = FakeMCP()
    dots.register(mcp, client)
    return mcp, client


def _run(routes: dict) -> dict:
    mcp, _ = _reg(routes)
    return asyncio.run(mcp.tools["dots_status"]())


def _conv(**extra: Any) -> dict:
    base = {"id": "c1", "title": "t", "is_automation_conversation": False}
    base.update(extra)
    return base


_ROUTES_ABSENT = {
    "/backend-api/conversations": {"items": [_conv(), _conv(id="c2")]},
    "/backend-api/models": {"models": [
        {"slug": "gpt-5-6"}, {"slug": "gpt-6-astra-wm", "title": "GPT-6 Astra"},
    ]},
    "/backend-api/accounts/check": {"accounts": {"a": {"entitlement": {}}}},
}


def test_not_rolled_out_without_markers() -> None:
    out = _run(_ROUTES_ABSENT)
    assert out["dots_detected"] is False
    assert out["status"] == "not_rolled_out"
    assert out["checked_conversations"] == 2
    assert out["automation_conversation_ids"] == []
    assert out["dot_named_fields"] == []
    # astra catalog presence alone must NOT claim dots
    assert out["astra_catalog_slugs"] == ["gpt-6-astra-wm"]


def test_detected_via_dot_named_field() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/accounts/check"] = {
        "accounts": {"a": {"entitlement": {}, "features": [{"dots_enabled": True}]}},
    }
    out = _run(routes)
    assert out["dots_detected"] is True
    assert out["status"] == "detected"
    assert any("dots_enabled" in p for p in out["dot_named_fields"])


def test_detected_via_conversation_origin() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/conversations"] = {"items": [
        _conv(conversation_origin={"type": "dot", "dot_id": "d1"}),
    ]}
    out = _run(routes)
    assert out["dots_detected"] is True
    assert out["unknown_conversation_origins"] == ["dot"]


def test_automation_conversation_is_candidate_not_detection() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/conversations"] = {"items": [
        _conv(id="auto1", is_automation_conversation=True),
        _conv(conversation_origin={"type": "custom_gpt"}),
    ]}
    out = _run(routes)
    assert out["dots_detected"] is False
    assert out["automation_conversation_ids"] == ["auto1"]
    # known origin types stay silent
    assert out["unknown_conversation_origins"] == []


def test_empty_and_malformed_payloads_do_not_crash() -> None:
    out = _run({
        "/backend-api/conversations": {},
        "/backend-api/models": {"models": "not-a-list"},
        "/backend-api/accounts/check": None,
    })
    assert out["dots_detected"] is False
    assert out["checked_conversations"] == 0
    assert out["astra_catalog_slugs"] == []


def test_three_readonly_gets_no_posts() -> None:
    mcp, client = _reg(_ROUTES_ABSENT)
    asyncio.run(mcp.tools["dots_status"]())
    assert len(client.gets) == 3
    assert all(g.startswith("/backend-api/") for g in client.gets)
