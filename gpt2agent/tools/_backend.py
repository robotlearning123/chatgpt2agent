from __future__ import annotations

import asyncio
from typing import Any

from gpt2agent.backend import BackendClient


async def async_get(client: BackendClient, path: str, **kwargs: Any) -> Any:
    """Run the synchronous backend GET without blocking the MCP event loop."""
    return await asyncio.to_thread(client.get, path, **kwargs)


async def async_post(client: BackendClient, path: str, **kwargs: Any) -> Any:
    """Run the synchronous backend POST without blocking the MCP event loop."""
    return await asyncio.to_thread(client.post, path, **kwargs)
