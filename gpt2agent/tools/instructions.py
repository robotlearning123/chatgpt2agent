from __future__ import annotations

from gpt2agent.backend import BackendClient
from gpt2agent.tools._backend import async_get
from gpt2agent.tools._redact import redact


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    async def custom_instructions_get() -> dict:
        """Return ChatGPT custom instructions (PII redacted)."""
        ci = await async_get(
            client,
            "/backend-api/user_system_messages",
            target_path="/backend-api/user_system_messages",
        ) or {}
        return {
            "enabled": ci.get("enabled"),
            "traits_enabled": ci.get("traits_enabled"),
            "personality_type": ci.get("personality_type_selection"),
            "about_user": redact(ci.get("about_user_message") or ""),
            "about_model": redact(ci.get("about_model_message") or ""),
        }
