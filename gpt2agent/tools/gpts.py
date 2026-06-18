from __future__ import annotations

from gpt2agent.backend import BackendClient
from gpt2agent.tools._redact import redact


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    def list_custom_gpts() -> list:
        """List your private Custom GPTs from the ChatGPT sidebar.

        Returns a list of ``{"name", "short_url"}``. Pass a returned
        ``short_url`` as the ``gizmo_id`` argument of ``gpt_chat`` to talk to
        that Custom GPT.
        """
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
