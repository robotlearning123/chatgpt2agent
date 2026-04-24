from __future__ import annotations

from openai_mcp.backend import BackendClient
from openai_mcp.tools._redact import redact


def _fetch_memories(client: BackendClient) -> list[dict]:
    data = client.get("/backend-api/memories", target_path="/backend-api/memories")
    return data.get("memories") or []


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    def memory_list() -> list:
        """Return all ChatGPT memories (PII redacted)."""
        return [
            {
                "id": m.get("id"),
                "status": m.get("status"),
                "content": redact(m.get("content") or ""),
                "created_timestamp": m.get("created_timestamp"),
            }
            for m in _fetch_memories(client)
        ]

    @mcp.tool()
    def memory_search(query: str) -> list:
        """Keyword search over ChatGPT memories. Returns matching entries (PII redacted)."""
        q = query.lower()
        return [
            {
                "id": m.get("id"),
                "content": redact(m.get("content") or ""),
                "created_timestamp": m.get("created_timestamp"),
            }
            for m in _fetch_memories(client)
            if q in (m.get("content") or "").lower()
        ]
