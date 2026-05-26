from __future__ import annotations

from gpt2agent.backend import BackendClient
from gpt2agent.tools._redact import redact


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    def account_status() -> dict:
        """Return ChatGPT account info: subscription plan, features, and model list."""
        me = client.get("/backend-api/me", target_path="/backend-api/me")
        check = client.get(
            "/backend-api/accounts/check/v4-2023-04-27",
            target_path="/backend-api/accounts/check/v4-2023-04-27",
        )
        acc_keys = list((check.get("accounts") or {}).keys())
        first = (check.get("accounts") or {}).get(acc_keys[0], {}) if acc_keys else {}
        ent = first.get("entitlement") or {}
        return {
            "email": redact(me.get("email") or ""),
            "country": me.get("country"),
            "groups": me.get("groups"),
            "subscription": ent.get("subscription_plan"),
            "has_active_subscription": ent.get("has_active_subscription"),
            "expires_at": ent.get("expires_at"),
            "features_count": len(first.get("features") or []),
        }

    @mcp.tool()
    def list_models() -> list:
        """Return all available ChatGPT models with full metadata."""
        data = client.get(
            "/backend-api/models?history_and_training_disabled=false",
            target_path="/backend-api/models",
        )
        return [
            {
                "slug": m.get("slug"),
                "title": m.get("title"),
                "description": m.get("description"),
                "max_tokens": m.get("max_tokens"),
                "reasoning_type": m.get("reasoning_type"),
                "thinking_efforts": m.get("thinking_efforts"),
                "tags": m.get("tags"),
                "capabilities": m.get("capabilities"),
                "enabled_tools": m.get("enabled_tools"),
                "product_features_keys": m.get("product_features_keys"),
            }
            for m in (data.get("models") or [])
        ]
