from __future__ import annotations

from openai_mcp.backend import BackendClient
from openai_mcp.tools import (
    account,
    apps,
    codex,
    conversations,
    gpts,
    instructions,
    memory,
)


def register_all(mcp, client: BackendClient) -> None:
    """Register every backend tool on *mcp*."""
    account.register(mcp, client)
    memory.register(mcp, client)
    instructions.register(mcp, client)
    codex.register(mcp, client)
    gpts.register(mcp, client)
    conversations.register(mcp, client)
    apps.register(mcp, client)
