from __future__ import annotations

from openai_mcp.backend import BackendClient
from openai_mcp.tools._redact import redact


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    def list_conversations(limit: int = 20) -> list:
        """Return recent ChatGPT conversations (titles PII-redacted)."""
        data = client.get(
            f"/backend-api/conversations?offset=0&limit={limit}&order=updated",
            target_path="/backend-api/conversations",
        )
        return [
            {
                "id": c.get("id"),
                "title": redact(c.get("title") or ""),
                "update_time": c.get("update_time"),
                "is_archived": c.get("is_archived"),
                "gizmo_id": c.get("gizmo_id"),
            }
            for c in (data.get("items") or [])
        ]

    @mcp.tool()
    def list_tasks(limit: int = 20) -> list:
        """Return scheduled/completed ChatGPT tasks (titles PII-redacted)."""
        data = client.get(
            f"/backend-api/tasks?limit={limit}",
            target_path="/backend-api/tasks",
        )
        return [
            {
                "title": redact(t.get("title") or ""),
                "status": t.get("status"),
                "created_at": t.get("created_at"),
            }
            for t in (data.get("tasks") or [])[:limit]
        ]
