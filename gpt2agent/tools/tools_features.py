"""Code interpreter and canvas execution tools."""
from __future__ import annotations

from gpt2agent.backend import BackendClient


def register(mcp, client: BackendClient) -> None:

    @mcp.tool()
    async def code_interpreter(
        prompt: str,
        model: str = "gpt-5-3",
    ) -> dict:
        """Execute code via ChatGPT's code interpreter.

        Sends a prompt that triggers code execution. The server runs the code
        in a sandbox and returns the output.

        Args:
            prompt: The code or instruction to execute (e.g. "Run this Python code: ...").
            model: ChatGPT model to use. Defaults to gpt-5-3.

        Returns:
            Dict with: conversation_id, text (assistant explanation),
            tool_calls, tool_responses, multimodal_assets (if any charts/images).
        """
        from gpt2agent.sse import ConversationClient

        conv = ConversationClient(client)
        return await conv.tool_call(prompt, model=model, temporary=False)

    @mcp.tool()
    async def canvas_execute(
        prompt: str,
        model: str = "gpt-5-3",
    ) -> dict:
        """Execute code via ChatGPT's Canvas feature.

        Creates a Canvas document with live code execution. Similar to
        code_interpreter but uses the Canvas editing environment.

        Args:
            prompt: The code or instruction (e.g. "Create a React component that...").
            model: ChatGPT model to use. Defaults to gpt-5-3.

        Returns:
            Dict with: conversation_id, text, tool_calls, tool_responses.
        """
        from gpt2agent.sse import ConversationClient

        conv = ConversationClient(client)
        return await conv.tool_call(
            f"Use Canvas to: {prompt}", model=model, temporary=False
        )
