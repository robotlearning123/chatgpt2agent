"""Unit tests for the dots tools — no network.

Two layers: (1) detection must be capable of a positive (a marker flips
`dots_detected`) so that a live "not_rolled_out" result carries power — the
negative-result rule from the anti-hallucination standard; (2) the automation
write tools must build exactly the wire shapes verified by execution
2026-10-04 (title required, schedule = full VEVENT string, timing_mode = 0,
set_status uses jawbone_id, remove uses automation_id).
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
    def __init__(self, routes: dict | None = None, posts: dict | None = None) -> None:
        self.routes = routes or {}
        self.posts = posts or {}
        self.gets: list[str] = []
        self.posted: list[tuple[str, Any]] = []

    def get(self, path: str, target_path: str | None = None, **k: Any) -> Any:
        self.gets.append(path)
        # longest-prefix match wins, mirroring real route resolution
        for pat in sorted(self.routes, key=len, reverse=True):
            if path == pat or path.startswith(pat):
                return self.routes[pat]
        return {}

    def post(self, path: str, json: Any = None, target_path: str | None = None, **k: Any) -> Any:
        self.posted.append((path, json))
        h = self.posts.get(path)
        if callable(h):
            return h(json)
        return h if h is not None else {"ok": True}


def _reg(routes: dict | None = None, posts: dict | None = None) -> tuple[FakeMCP, FakeClient]:
    client = FakeClient(routes, posts)
    mcp = FakeMCP()
    dots.register(mcp, client)
    return mcp, client


def _run(mcp: FakeMCP, name: str, /, **kw: Any) -> Any:
    return asyncio.run(mcp.tools[name](**kw))


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
    "/backend-api/automations": {"items": []},
}


def test_not_rolled_out_without_markers() -> None:
    mcp, _ = _reg(_ROUTES_ABSENT)
    out = _run(mcp, "dots_status")
    assert out["dots_detected"] is False
    assert out["status"] == "not_rolled_out"
    assert out["checked_conversations"] == 2
    assert out["automation_conversation_ids"] == []
    assert out["dot_named_fields"] == []
    # astra catalog presence alone must NOT claim dots
    assert out["astra_catalog_slugs"] == ["gpt-6-astra-wm"]
    assert out["automations"] == {"total": 0, "cloud_executor": 0, "with_aeon_id": 0,
                                  "note": out["automations"]["note"]}


def test_detected_via_dot_named_field() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/accounts/check"] = {
        "accounts": {"a": {"entitlement": {}, "features": [{"dots_enabled": True}]}},
    }
    mcp, _ = _reg(routes)
    out = _run(mcp, "dots_status")
    assert out["dots_detected"] is True
    assert out["status"] == "detected"
    assert any("dots_enabled" in p for p in out["dot_named_fields"])


def test_detected_via_conversation_origin() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/conversations"] = {"items": [
        _conv(conversation_origin={"type": "dot", "dot_id": "d1"}),
    ]}
    mcp, _ = _reg(routes)
    out = _run(mcp, "dots_status")
    assert out["dots_detected"] is True
    assert out["unknown_conversation_origins"] == ["dot"]


def test_automation_conversation_is_candidate_not_detection() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/conversations"] = {"items": [
        _conv(id="auto1", is_automation_conversation=True),
        _conv(conversation_origin={"type": "custom_gpt"}),
        _conv(id="tpp1", conversation_origin={"type": "tpp"}),
    ]}
    mcp, _ = _reg(routes)
    out = _run(mcp, "dots_status")
    assert out["dots_detected"] is False
    assert out["automation_conversation_ids"] == ["auto1"]
    assert out["unknown_conversation_origins"] == []


def test_status_counts_cloud_automations() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/automations"] = {"items": [
        {"id": "a1", "executor": "cloud", "aeon_id": "u~1"},
        {"id": "a2", "executor": "cloud", "aeon_id": None},
        {"id": "a3", "executor": "local"},
    ]}
    mcp, _ = _reg(routes)
    out = _run(mcp, "dots_status")
    assert out["automations"]["total"] == 3
    assert out["automations"]["cloud_executor"] == 2
    assert out["automations"]["with_aeon_id"] == 1


def test_empty_and_malformed_payloads_do_not_crash() -> None:
    mcp, _ = _reg({
        "/backend-api/conversations": {},
        "/backend-api/models": {"models": "not-a-list"},
        "/backend-api/accounts/check": None,
        "/backend-api/automations": {},
    })
    out = _run(mcp, "dots_status")
    assert out["dots_detected"] is False
    assert out["checked_conversations"] == 0
    assert out["astra_catalog_slugs"] == []
    assert out["automations"]["total"] == 0


def test_four_readonly_gets_no_writes_in_status() -> None:
    mcp, client = _reg(_ROUTES_ABSENT)
    asyncio.run(mcp.tools["dots_status"]())
    assert len(client.gets) == 4
    assert all(g.startswith("/backend-api/") for g in client.gets)
    assert client.posted == []


def test_list_automations_redacts_truncates_limits() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/automations"] = {"items": [
        {"id": f"a{i}", "title": f"t{i} user@example.com", "prompt": "p" * 500,
         "is_enabled": True, "executor": "cloud", "timing_mode": "exact_schedule",
         "schedule": "BEGIN:VEVENT\nDTSTART:x\nRRULE:FREQ=DAILY\nEND:VEVENT",
         "next_run_times": ["t1", "t2", "t3", "t4"], "can_delete": True}
        for i in range(5)
    ]}
    mcp, _ = _reg(routes)
    out = _run(mcp, "list_automations", limit=3)
    assert len(out) == 3
    assert out[0]["prompt"].endswith("…") and len(out[0]["prompt"]) <= 281
    assert "user@example.com" not in out[0]["title"]
    assert "\n" not in out[0]["schedule"]
    assert len(out[0]["next_run_times"]) == 3


def test_create_automation_builds_verified_wire_shape() -> None:
    mcp, client = _reg(_ROUTES_ABSENT)
    out = _run(mcp, "create_automation", prompt="check things", title="my check",
               timezone="America/New_York")
    path, body = client.posted[0]
    assert path == "/backend-api/automations/save"
    assert body["title"] == "my check"
    assert body["prompt"] == "check things"
    assert body["timing_mode"] == 0
    assert body["executor"] == "cloud"
    assert body["is_enabled"] is False  # created paused by default
    assert body["schedule"].startswith("BEGIN:VEVENT\nDTSTART:")
    assert "\nRRULE:FREQ=DAILY;BYHOUR=3;BYMINUTE=0\n" in body["schedule"]
    assert body["schedule"].endswith("END:VEVENT")
    assert "model" not in body and "reasoning_effort" not in body
    assert body["default_timezone"] == "America/New_York"
    assert out == {"ok": True}


def test_create_automation_raw_rrule_and_title_default() -> None:
    mcp, client = _reg(_ROUTES_ABSENT)
    _run(mcp, "create_automation", prompt="x" * 80, rrule="FREQ=MINUTELY;INTERVAL=10",
         model="gpt-6-pro", reasoning_effort="high", enabled=True)
    _, body = client.posted[0]
    assert body["title"] == "x" * 60
    assert "RRULE:FREQ=MINUTELY;INTERVAL=10" in body["schedule"]
    assert body["is_enabled"] is True
    assert body["model"] == "gpt-6-pro"
    assert body["reasoning_effort"] == "high"


def test_set_status_uses_jawbone_id() -> None:
    mcp, client = _reg(_ROUTES_ABSENT)
    _run(mcp, "set_automation_status", automation_id="abc", enabled=True)
    path, body = client.posted[0]
    assert path == "/backend-api/automations/set_status"
    assert body == {"jawbone_id": "abc", "is_enabled": True}


def test_remove_uses_automation_id() -> None:
    mcp, client = _reg(_ROUTES_ABSENT)
    _run(mcp, "remove_automation", automation_id="abc")
    path, body = client.posted[0]
    assert path == "/backend-api/automations/remove"
    assert body == {"automation_id": "abc"}


def test_list_dots_joins_aeon_with_room() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/tbo"] = {"items": [
        {"id": "user~abc", "display_name": "Alfred"},
        {"id": "orphan", "display_name": ""},
    ]}
    routes["/backend-api/messaging/rooms"] = {"items": [
        {"id": "r1", "name": "dot", "type": "DM", "aeon_id": "user~abc", "updated_at": "t"},
    ]}
    mcp, _ = _reg(routes)
    out = _run(mcp, "list_dots")
    assert out == [
        {"aeon_id": "user~abc", "display_name": "Alfred", "room_id": "r1",
         "room_name": "dot", "room_updated_at": "t"},
        {"aeon_id": "orphan", "display_name": "", "room_id": None,
         "room_name": None, "room_updated_at": None},
    ]


def test_dot_messages_classifies_roles_sorts_and_redacts() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/messaging/rooms"] = {"items": [
        {"id": "r1", "aeon_id": "a1"},
    ]}
    routes["/backend-api/messaging/rooms/r1/messages"] = {"items": [
        {"created_at": "2026-10-04T02", "account_user_id": "calpico-member-abc",
         "content": {"text": "me@example.com done"}},
        {"created_at": "2026-10-04T01", "account_user_id": "user-X",
         "content": {"text": "hello"}},
    ]}
    mcp, _ = _reg(routes)
    out = _run(mcp, "dot_messages")
    assert [m["role"] for m in out] == ["OWNER", "DOT"]  # sorted by created_at
    assert "me@example.com" not in out[1]["text"]


def test_dot_messages_explicit_room_and_limit_cap() -> None:
    mcp, client = _reg(_ROUTES_ABSENT)
    _run(mcp, "dot_messages", room_id="r9", limit=99)
    assert client.gets[-1] == "/backend-api/messaging/rooms/r9/messages?limit=32"


def test_dot_messages_no_room_honest_error() -> None:
    mcp, _ = _reg(_ROUTES_ABSENT)
    out = _run(mcp, "dot_messages")
    assert "error" in out and "no dot room" in out["error"]
