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
    assert out["automations"]["total"] == 0
    assert out["automations"]["cloud_executor"] == 0
    assert out["automations"]["with_aeon_id"] == 0
    assert "set_automation_status" in out["automations"]["note"]
    assert out["errors"] == []


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
        _conv(conversation_origin={"type": "dot"}),
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
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/messaging/rooms"] = {"items": [{"id": "r9", "aeon_id": "a1"}]}
    mcp, client = _reg(routes)
    _run(mcp, "dot_messages", room_id="r9", limit=99)
    assert client.gets[0] == "/backend-api/messaging/rooms?limit=25"  # validated
    assert client.gets[-1] == "/backend-api/messaging/rooms/r9/messages?limit=32"


def test_dot_messages_rejects_unlinked_room() -> None:
    # A caller-supplied room that is not a dot DM must not silently read an
    # unrelated room (review 2026-10-04).
    mcp, client = _reg(_ROUTES_ABSENT)
    out = _run(mcp, "dot_messages", room_id="r-not-linked")
    assert out["status"] == "invalid_room"
    assert not any("/messages" in p for p in client.gets)


def test_send_to_dot_rejects_unlinked_room() -> None:
    mcp, client = _reg(_ROUTES_ABSENT)
    out = _run(mcp, "send_to_dot", text="hi", room_id="r-not-linked")
    assert out["delivered"] is False and out["status"] == "invalid_room"
    assert not client.posted


def test_dots_status_scans_envelope_and_models() -> None:
    # A dot-named key in the conversations envelope or the models payload is
    # a marker (review 2026-10-04) — detection must be capable of a positive
    # from either surface alone.
    for surface, payload in (
        ("conversations", {"dotted_features": {"dots": True}, "items": []}),
        ("models", {"models": [], "dots_beta": True}),
    ):
        routes = dict(_ROUTES_ABSENT)
        routes[f"/backend-api/{surface}"] = payload
        mcp, _ = _reg(routes)
        out = _run(mcp, "dots_status")
        assert out["dots_detected"] is True, surface
        assert out["status"] == "detected", surface


def test_dots_status_reports_incomplete_conversation_scan() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/conversations"] = {"items": [_conv(id=f"c{i}") for i in range(50)]}
    mcp, _ = _reg(routes)
    out = _run(mcp, "dots_status")
    assert out["checked_conversations"] == 50
    assert out["conversations_scan_complete"] is False


def test_list_dots_joins_room_beyond_old_window() -> None:
    # The join must consider the whole fetched page, not slice to `limit`
    # (review 2026-10-04: dot room outside a 10-room window joined as null).
    rooms = [{"id": f"r{i}", "aeon_id": None} for i in range(11)]
    rooms.append({"id": "r-dot", "aeon_id": "a1", "name": "dot dm"})
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/tbo"] = {"items": [{"id": "a1", "display_name": "D"}]}
    routes["/backend-api/messaging/rooms"] = {"items": rooms}
    mcp, _ = _reg(routes)
    out = _run(mcp, "list_dots", limit=10)
    assert out[0]["room_id"] == "r-dot" and out[0]["room_name"] == "dot dm"


def test_dot_messages_no_room_friendly_guidance() -> None:
    mcp, _ = _reg(_ROUTES_ABSENT)
    out = _run(mcp, "dot_messages")
    assert out["status"] == "no_dot"
    assert out["dots_available"] is False
    assert "desktop" in out["how_to_enable"] and "docs/dots.md" in out["how_to_enable"]


def test_dots_status_carries_friendly_hint() -> None:
    mcp, _ = _reg(_ROUTES_ABSENT)
    out = _run(mcp, "dots_status")
    assert "desktop" in out["hint"] and "docs/dots.md" in out["hint"]


def test_send_to_dot_delivered_despite_422() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/messaging/rooms"] = {"items": [{"id": "r1", "aeon_id": "a1"}]}
    state = {"items": [
        {"id": "m0", "created_at": "t0", "account_user_id": "user-X", "content": {"text": "old"}},
    ]}
    routes["/backend-api/messaging/rooms/r1/messages"] = state

    class AppendClient(FakeClient):
        def post(self, path, json=None, target_path=None, **k):
            self.posted.append((path, json))
            if path.endswith("/messages"):
                state["items"].append({"id": "m1", "created_at": "t1", "account_user_id": "user-X",
                                       "content": {"text": json["content"]["text"]}})
            raise RuntimeError('HTTP 422 for path: {"detail":"Messaging with the user\'s dot requires a stable send identifier"}')
    mcp = FakeMCP()
    dots.register(mcp, AppendClient(routes))
    out = _run(mcp, "send_to_dot", text="hello dot please reply")
    assert out["delivered"] is True and out["verified_in_room"] is True
    assert out["room_id"] == "r1"
    assert "dot_messages" in out["note"]


def test_send_to_dot_not_in_room_marks_undelivered() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/messaging/rooms"] = {"items": [{"id": "r1", "aeon_id": "a1"}]}
    routes["/backend-api/messaging/rooms/r1/messages"] = {"items": []}
    mcp, _ = _reg(routes)
    out = _run(mcp, "send_to_dot", text="hello")
    assert out["delivered"] is False


def test_send_to_dot_no_room_friendly() -> None:
    mcp, _ = _reg(_ROUTES_ABSENT)
    out = _run(mcp, "send_to_dot", text="hello")
    assert out["delivered"] is False and "desktop" in out["how_to_enable"]


def test_send_to_dot_reraises_non_422_errors() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/messaging/rooms"] = {"items": [{"id": "r1", "aeon_id": "a1"}]}

    class ErrClient(FakeClient):
        def post(self, path, json=None, target_path=None, **k):
            raise RuntimeError("HTTP 500 boom")

    mcp = FakeMCP()
    dots.register(mcp, ErrClient(routes))
    import pytest
    with pytest.raises(RuntimeError):
        asyncio.run(mcp.tools["send_to_dot"](text="hello"))


def test_rrule_per_frequency_no_collapse() -> None:
    mcp, client = _reg(_ROUTES_ABSENT)
    _run(mcp, "create_automation", prompt="h", frequency="hourly")
    _run(mcp, "create_automation", prompt="m", frequency="MINUTELY")
    _run(mcp, "create_automation", prompt="d", frequency="daily")
    rules = [b["schedule"].split("RRULE:")[1].split("\n")[0] for _, b in client.posted]
    assert rules[0] == "FREQ=HOURLY;BYMINUTE=0"
    assert rules[1] == "FREQ=MINUTELY"
    assert rules[2] == "FREQ=DAILY;BYHOUR=3;BYMINUTE=0"


def test_send_to_dot_stale_repeat_is_not_delivery() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/messaging/rooms"] = {"items": [{"id": "r1", "aeon_id": "a1"}]}
    state = {"items": [
        {"id": "m0", "created_at": "t0", "account_user_id": "user-X", "content": {"text": "hello"}},
    ]}
    routes["/backend-api/messaging/rooms/r1/messages"] = state

    class NoPersistClient(FakeClient):
        def post(self, path, json=None, target_path=None, **k):
            self.posted.append((path, json))  # 422 AND nothing persisted

    mcp = FakeMCP()
    dots.register(mcp, NoPersistClient(routes))
    out = _run(mcp, "send_to_dot", text="hello")  # identical text already in room
    assert out["delivered"] is False


def test_dots_status_falsy_dot_flag_is_not_detection() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/accounts/check"] = {
        "accounts": {"a": {"features": [{"dots_enabled": False}]}}}
    mcp, _ = _reg(routes)
    out = _run(mcp, "dots_status")
    assert out["dots_detected"] is False
    assert out["dot_named_fields"] == ["accounts_check.accounts.a.features[0].dots_enabled"]


def test_invalid_frequency_raises_not_silent_daily() -> None:
    import pytest
    mcp, client = _reg(_ROUTES_ABSENT)
    for bad in ("monthly", "yearly", "weekley", "weekly!", "WEEKLYx"):
        with pytest.raises(ValueError, match="frequency must be one of"):
            _run(mcp, "create_automation", prompt="p", frequency=bad)
    assert client.posted == []  # nothing reached the wire


def test_frequency_whitespace_and_case_normalized() -> None:
    mcp, client = _reg(_ROUTES_ABSENT)
    _run(mcp, "create_automation", prompt="p", frequency=" Weekly ")
    _, body = client.posted[0]
    assert "RRULE:FREQ=WEEKLY;BYHOUR=3;BYMINUTE=0" in body["schedule"]


def test_empty_dot_container_is_not_detection() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/accounts/check"] = {
        "accounts": {"a": {"features": [{"dots": {}}]}}}
    mcp, _ = _reg(routes)
    out = _run(mcp, "dots_status")
    assert out["dots_detected"] is False
    # a NON-empty container still detects
    routes["/backend-api/accounts/check"] = {
        "accounts": {"a": {"features": [{"dots": {"enabled": True}}]}}}
    mcp, _ = _reg(routes)
    out = _run(mcp, "dots_status")
    assert out["dots_detected"] is True


def test_dots_status_degrades_on_partial_endpoint_failure() -> None:
    routes = dict(_ROUTES_ABSENT)

    class FlakyClient(FakeClient):
        def get(self, path, target_path=None, **k):
            if path.startswith("/backend-api/automations"):
                raise RuntimeError("HTTP 500 for automations")
            return super().get(path, target_path, **k)

    mcp = FakeMCP()
    dots.register(mcp, FlakyClient(routes))
    out = _run(mcp, "dots_status")
    assert out["dots_detected"] is False  # still answers
    assert any("automations" in e for e in out["errors"])
    assert out["checked_conversations"] == 2  # other surfaces intact


def test_prompt_cap_asserts_both_sides() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/automations"] = {"items": [
        {"id": "a1", "title": "t", "prompt": "p" * 500},
    ]}
    mcp, _ = _reg(routes)
    out = _run(mcp, "list_automations")
    assert len(out[0]["prompt"]) == 281  # 280 + ellipsis
    assert out[0]["prompt"].startswith("pppp")


def test_nested_off_flag_is_not_detection() -> None:
    routes = dict(_ROUTES_ABSENT)
    routes["/backend-api/accounts/check"] = {
        "accounts": {"a": {"features": [{"dots": {"enabled": False}}]}}}
    mcp, _ = _reg(routes)
    assert _run(mcp, "dots_status")["dots_detected"] is False
    routes["/backend-api/accounts/check"] = {
        "accounts": {"a": {"features": [{"dots": {"enabled": False, "id": "d1"}}]}}}
    mcp, _ = _reg(routes)
    assert _run(mcp, "dots_status")["dots_detected"] is True  # a truthy leaf counts


def test_total_upstream_failure_is_unknown_not_absent() -> None:
    class DeadClient(FakeClient):
        def get(self, path, target_path=None, **k):
            raise RuntimeError("HTTP 401 Unauthorized — token expired")

    mcp = FakeMCP()
    dots.register(mcp, DeadClient(dict(_ROUTES_ABSENT)))
    out = _run(mcp, "dots_status")
    assert out["dots_detected"] is False
    assert out["status"] == "unknown_upstream_error"
    assert "NOT a 'no dots' verdict" in out["hint"] and "4 of 4" in out["hint"]
    assert len(out["errors"]) == 4


def test_any_failed_surface_makes_negative_unknown() -> None:
    # Even 1 of 4 surfaces failing (esp. conversations, the primary
    # detection surface) must not yield a confident "not_rolled_out".
    routes = dict(_ROUTES_ABSENT)

    class OneDeadClient(FakeClient):
        def get(self, path, target_path=None, **k):
            if path.startswith("/backend-api/conversations"):
                raise RuntimeError("HTTP 401 Unauthorized")
            return super().get(path, target_path, **k)

    mcp = FakeMCP()
    dots.register(mcp, OneDeadClient(routes))
    out = _run(mcp, "dots_status")
    assert out["status"] == "unknown_upstream_error"
    assert "1 of 4" in out["hint"]
    assert len(out["errors"]) == 1
    assert out["dots_detected"] is False


def test_has_on_value_depth_bounded() -> None:
    deep = cur = {}
    for _ in range(500):
        cur["n"] = {}
        cur = cur["n"]
    cur["n"] = True
    assert dots._has_on_value({"dots": deep}) is False  # no RecursionError, depth-capped
    assert dots._has_on_value({"dots": {"a": {"b": True}}}) is True
