from __future__ import annotations

from gpt2agent.backend import BackendClient
from gpt2agent.tools._redact import redact


def register(mcp, client: BackendClient) -> None:
    @mcp.tool()
    def list_conversations(limit: int = 20) -> list:
        """Return recent ChatGPT conversations (titles PII-redacted)."""
        data = client.get(
            f"/backend-api/conversations?offset=0&limit={limit}&order=updated",
            target_path="/backend-api/conversations",
        )
        return [
            {
                "id": c.get("id"),
                "title": redact(c.get("title") or ""),
                "update_time": c.get("update_time"),
                "is_archived": c.get("is_archived"),
                "gizmo_id": c.get("gizmo_id"),
            }
            for c in (data.get("items") or [])
        ]

    @mcp.tool()
    def get_conversation(conversation_id: str, max_messages: int = 100) -> dict:
        """Get full details of a ChatGPT conversation including all messages.

        Args:
            conversation_id: The conversation ID.
            max_messages: Maximum number of messages to return (default 100).

        Returns:
            Dict with title, create_time, mapping (all messages), and metadata.
        """
        data = client.get(f"/backend-api/conversation/{conversation_id}")
        if not data:
            return {}
        messages = []
        for node_id, node in (data.get("mapping") or {}).items():
            msg = (node or {}).get("message")
            if not isinstance(msg, dict):
                continue
            role = (msg.get("author") or {}).get("role", "")
            if role not in ("user", "assistant", "tool"):
                continue
            content = msg.get("content") or {}
            ct = content.get("content_type", "")
            parts = content.get("parts") or []
            entry = {
                "id": msg.get("id"),
                "role": role,
                "recipient": msg.get("recipient"),
                "content_type": ct,
                "status": msg.get("status"),
                "create_time": msg.get("create_time"),
            }
            if ct in ("text", "multimodal_text") and parts:
                str_parts = [p for p in parts if isinstance(p, str)]
                if str_parts:
                    entry["text"] = str_parts[0][:2000]
                # Check for image assets in multimodal parts
                img_parts = [p for p in parts if isinstance(p, dict) and p.get("content_type") == "image_asset_pointer"]
                if img_parts:
                    entry["images"] = [
                        {
                            "asset_pointer": p.get("asset_pointer"),
                            "width": p.get("width"),
                            "height": p.get("height"),
                        }
                        for p in img_parts
                    ]
            elif ct == "code" and parts and isinstance(parts[0], str):
                entry["code"] = parts[0][:500]
            messages.append(entry)
            if len(messages) >= max_messages:
                break
            "id": data.get("id"),
            "title": redact(data.get("title") or ""),
            "create_time": data.get("create_time"),
            "update_time": data.get("update_time"),
            "message_count": len(messages),
            "messages": messages,
        }

    @mcp.tool()
    def list_tasks(limit: int = 20) -> list:
        """Return scheduled/completed ChatGPT tasks with full metadata (titles PII-redacted)."""
        data = client.get(
            f"/backend-api/tasks?limit={limit}",
            target_path="/backend-api/tasks",
        )
        return [
            {
                "task_id": t.get("task_id"),
                "title": redact(t.get("title") or ""),
                "status": t.get("status"),
                "created_at": t.get("created_at"),
                "updated_at": t.get("updated_at"),
                "prompt": redact(t.get("prompt") or ""),
                "conversation_id": t.get("conversation_id"),
                "image_gen_message": t.get("image_gen_message") is not None,
                "interruptions_disabled": t.get("interruptions_disabled"),
            }
            for t in (data.get("tasks") or [])[:limit]
        ]
