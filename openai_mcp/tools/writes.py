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
        payload = {**current}
        if about_user is not None:
            payload["about_user_message"] = about_user
        if about_model is not None:
            payload["about_model_message"] = about_model
        return client.post(
            "/backend-api/user_system_messages",
            json=payload,
            target_path="/backend-api/user_system_messages",
        )

    # memory_add is NOT registered as an MCP tool.
    # SPIKE FINDING 2026-04-23: POST /backend-api/memories → 405 Method Not Allowed
    # (Allow: GET only). PATCH and PUT also 405. Memory creation is model-initiated
    # only — not available via REST. Exposing a tool that always raises misleads agents
    # that introspect the tool list, so registration is intentionally skipped.
    def memory_add(content: str) -> dict:  # noqa: F841 — kept as documentation
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
        branch: str = "main",
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
            matches = [e for e in envs if e.get("label") == repo_label]
            if len(matches) == 0:
                available = [e.get("label") for e in envs]
                raise ValueError(
                    f"No Codex environment with label {repo_label!r}. Available: {available}"
                )
            if len(matches) > 1:
                ids = [e.get("id") for e in matches]
                raise ValueError(
                    f"Ambiguous label {repo_label!r}: matches {len(matches)} environments "
                    f"({ids}). Pass environment_id explicitly."
                )
            env_id = matches[0]["id"]

        payload = {
            "new_task": {
                "environment_id": env_id,
                "branch": branch,
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
