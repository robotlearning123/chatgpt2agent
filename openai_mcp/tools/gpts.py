from __future__ import annotations

from openai_mcp.backend import BackendClient
from openai_mcp.tools._redact import redact


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    def list_custom_gpts() -> list:
        """Return private custom GPTs from the ChatGPT sidebar."""
        data = client.get(
            "/backend-api/gizmos/snorlax/sidebar",
            target_path="/backend-api/gizmos/snorlax/sidebar",
        )
        return [
            {
                "name": redact((item.get("gizmo") or {}).get("name") or ""),
                "short_url": (item.get("gizmo") or {}).get("short_url"),
            }
            for item in (data.get("items") or [])
        ]
