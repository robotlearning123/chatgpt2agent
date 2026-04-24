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

    @mcp.tool()
    def memory_add(content: str) -> dict:
        """Add a new ChatGPT memory.

        SPIKE FINDING 2026-04-23: POST /backend-api/memories returns 405
        Method Not Allowed (Allow: GET only). PATCH and PUT also 405.
        Memory creation is model-initiated only — not available via REST.
        """
        # POST → 405, PATCH → 405, PUT → 405, OPTIONS → Allow: GET
        raise RuntimeError(
            "POST /backend-api/memories is not supported — server returns 405 "
            "Method Not Allowed (Allow: GET). Memory creation must go through "
            "a ChatGPT conversation (model-initiated only)."
        )

    @mcp.tool()
    def codex_task_create(
        repo_label: str,
        prompt: str,
        environment_id: str | None = None,
    ) -> dict:
        """Create a new Codex task.

        Resolves environment_id from repo_label if not supplied.
        Verified payload shape (2026-04-23): POST /backend-api/codex/tasks
        with new_task={environment_id, branch} + top-level input_items.
        """
        env_id = environment_id
        if env_id is None:
            data = client.get(
                "/backend-api/codex/environments",
                target_path="/backend-api/codex/environments",
            )
            envs = data if isinstance(data, list) else (data.get("environments") or [])
            match = next((e for e in envs if e.get("label") == repo_label), None)
            if match is None:
                available = [e.get("label") for e in envs]
                raise ValueError(
                    f"No Codex environment with label {repo_label!r}. Available: {available}"
                )
            env_id = match["id"]

        payload = {
            "new_task": {
                "environment_id": env_id,
                "branch": "main",
            },
            "input_items": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"content_type": "text", "text": prompt}],
                }
            ],
        }
        return client.post(
            "/backend-api/codex/tasks",
            json=payload,
            target_path="/backend-api/codex/tasks",
        )
