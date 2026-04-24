from __future__ import annotations

from openai_mcp.backend import BackendClient


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    def custom_instructions_set(
        about_user: str | None = None,
        about_model: str | None = None,
    ) -> dict:
        """Overwrite ChatGPT custom instructions (read-modify-write — preserves fields not supplied)."""
        current = client.get(
            "/backend-api/user_system_messages",
            target_path="/backend-api/user_system_messages",
        )
        payload = {
            "enabled": current.get("enabled"),
            "about_user_message": about_user
            if about_user is not None
            else current.get("about_user_message", ""),
            "about_model_message": about_model
            if about_model is not None
            else current.get("about_model_message", ""),
            "traits_enabled": current.get("traits_enabled"),
            "personality_type_selection": current.get("personality_type_selection"),
            "disabled_tools": current.get("disabled_tools") or [],
        }
        return client.post(
            "/backend-api/user_system_messages",
            json=payload,
            target_path="/backend-api/user_system_messages",
        )
