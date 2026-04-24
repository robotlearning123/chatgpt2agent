from __future__ import annotations

from openai_mcp.backend import BackendClient
from openai_mcp.tools._redact import redact


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    def list_codex_envs() -> list:
        """Return Codex environments (label, repos, network access)."""
        data = client.get(
            "/backend-api/codex/environments",
            target_path="/backend-api/codex/environments",
        )
        envs = data if isinstance(data, list) else (data.get("environments") or [])
        return [
            {
                "id": e.get("id"),
                "label": e.get("label"),
                "workspace_dir": e.get("workspace_dir"),
                "agent_network_access": e.get("agent_network_access"),
                "repo_count": len(e.get("repos") or []),
            }
            for e in envs
        ]

    @mcp.tool()
    def list_codex_tasks(limit: int = 10) -> list:
        """Return recent Codex tasks (title + status). Content is PII-redacted."""
        data = client.get(
            f"/backend-api/codex/tasks?limit={limit}",
            target_path="/backend-api/codex/tasks",
        )
        items = data.get("items") or []
        return [
            {
                "id": (t.get("task") or t).get("id") if isinstance(t, dict) else None,
                "title": redact(
                    ((t.get("task") or t).get("title") or "")
                    if isinstance(t, dict)
                    else ""
                ),
                "status": (t.get("turn") or {}).get("turn_status")
                if isinstance(t, dict)
                else None,
            }
            for t in items[:limit]
        ]
