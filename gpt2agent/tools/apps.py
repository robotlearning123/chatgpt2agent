from __future__ import annotations

from gpt2agent.backend import BackendClient


def _classify(app_id: str) -> str:
    if app_id.startswith("connector_"):
        return "official_connector"
    if app_id.startswith("asdk_app_"):
        return "third_party_sdk"
    return "unknown"


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    def list_apps() -> list:
        """Return ChatGPT connected apps/connectors. Names unresolvable — IDs with type classification returned."""
        data = client.get(
            "/backend-api/apps/list",
            target_path="/backend-api/apps/list",
        ) or {}
        return [
            {
                "id": a.get("id"),
                "type": _classify(a.get("id") or ""),
                "enabled": a.get("enabled"),
                # Check key presence, not truthiness: `is_connected: False` (a
                # disconnected app) must report False, not fall through to
                # `connected` or None.
                "connected": (
                    a["is_connected"] if "is_connected" in a else a.get("connected")
                ),
            }
            for a in (data.get("apps") or [])
            if isinstance(a, dict)
        ]
