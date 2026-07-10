from __future__ import annotations

from gpt2agent.backend import BackendClient
from gpt2agent.tools._backend import async_get
from gpt2agent.tools._redact import redact


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    async def list_codex_envs() -> list:
        """Return Codex environments (label, repos, network access)."""
        data = await async_get(
            client,
            "/backend-api/codex/environments",
            target_path="/backend-api/codex/environments",
        ) or {}
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
    async def list_codex_tasks(limit: int = 10) -> list:
        """Return recent Codex tasks (title + status). Content is PII-redacted."""
        data = await async_get(
            client,
            f"/backend-api/codex/tasks?limit={limit}",
            target_path="/backend-api/codex/tasks",
        ) or {}
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
