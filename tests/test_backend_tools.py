"""Integration test: BackendClient.account_status() against live chatgpt.com.

Skipped automatically when ~/.codex/auth.json is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.skipif(
    not (Path.home() / ".codex" / "auth.json").exists(),
    reason="~/.codex/auth.json not present",
)
def test_account_status_has_subscription() -> None:
    from openai_mcp.backend import BackendClient

    client = BackendClient()

    # call the raw backend methods directly — no MCP runtime needed
    me = client.get("/backend-api/me", target_path="/backend-api/me")
    check = client.get(
        "/backend-api/accounts/check/v4-2023-04-27",
        target_path="/backend-api/accounts/check/v4-2023-04-27",
    )

    acc_keys = list((check.get("accounts") or {}).keys())
    assert acc_keys, "accounts dict is empty"
    first = (check.get("accounts") or {}).get(acc_keys[0], {})
    ent = first.get("entitlement") or {}

    assert "subscription_plan" in ent, f"subscription field missing; entitlement={ent}"
    assert ent.get("subscription_plan"), "subscription_plan is empty"
