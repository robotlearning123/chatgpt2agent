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
        ) or {}
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
        mapping = data.get("mapping") or {}
        # Walk the active branch from the leaf (`current_node`) up to the root via
        # parent pointers, then reverse to chronological order. Raw `mapping`
        # iteration order interleaves sibling branches of an edited/regenerated
        # conversation and, combined with the max_messages cap, can drop visible
        # turns. Fall back to a create_time sort when current_node is missing.
        ordered_nodes: list = []
        current = data.get("current_node")
        if current and current in mapping:
            seen_ids: set[str] = set()
            nid = current
            while nid and nid in mapping and nid not in seen_ids:
                seen_ids.add(nid)
                ordered_nodes.append(mapping[nid])
                nid = (mapping[nid] or {}).get("parent")
            ordered_nodes.reverse()
        else:
            ordered_nodes = sorted(
                (n for n in mapping.values() if isinstance(n, dict)),
                key=lambda n: ((n.get("message") or {}).get("create_time") or 0),
            )

        messages = []
        for node in ordered_nodes:
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

        return {
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
        ) or {}
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
