from __future__ import annotations

from openai_mcp.backend import BackendClient
from openai_mcp.tools._redact import redact


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    def custom_instructions_get() -> dict:
        """Return ChatGPT custom instructions (PII redacted)."""
        ci = client.get(
            "/backend-api/user_system_messages",
            target_path="/backend-api/user_system_messages",
        )
        return {
            "enabled": ci.get("enabled"),
            "traits_enabled": ci.get("traits_enabled"),
            "personality_type": ci.get("personality_type_selection"),
            "about_user": redact(ci.get("about_user_message") or ""),
            "about_model": redact(ci.get("about_model_message") or ""),
        }
