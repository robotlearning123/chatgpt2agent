from __future__ import annotations

from gpt2agent.backend import BackendClient
from gpt2agent.tools._backend import async_get
from gpt2agent.tools._redact import redact


async def _fetch_memories(client: BackendClient) -> list[dict]:
    data = await async_get(
        client,
        "/backend-api/memories",
        target_path="/backend-api/memories",
    )
    return (data or {}).get("memories") or []


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    async def memory_list() -> list:
        """Return all ChatGPT memories (PII redacted)."""
        return [
            {
                "id": m.get("id"),
                "status": m.get("status"),
                "content": redact(m.get("content") or ""),
                "created_timestamp": m.get("created_timestamp"),
            }
            for m in await _fetch_memories(client)
        ]

    @mcp.tool()
    async def memory_search(query: str) -> list:
        """Keyword search over ChatGPT memories. Returns matching entries (PII redacted)."""
        q = query.lower()
        matches = []
        for m in await _fetch_memories(client):
            content = redact(m.get("content") or "")
            if q in content.lower():
                matches.append(
                    {
                        "id": m.get("id"),
                        "content": content,
                        "created_timestamp": m.get("created_timestamp"),
                    }
                )
        return matches
