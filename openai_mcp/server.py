"""openai-mcp — MCP server backed by native chatgpt.com SSE client."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from mcp.server.fastmcp import FastMCP

# ── config ──────────────────────────────────────────────────────────────────

_CONFIG_SEARCH = [
    Path.home() / ".openai-mcp" / "config.toml",
    Path("config.toml"),
    Path.home() / ".config" / "openai-mcp" / "config.toml",
]

_DEFAULTS: dict[str, Any] = {
    "server": {"host": "0.0.0.0", "port": 9000},
    "models": {"chat": "gpt-5-3"},
}


def load_config(path: Path | None = None) -> dict[str, Any]:
    candidates = [path] if path else _CONFIG_SEARCH
    for p in candidates:
        if p and p.exists():
            with open(p, "rb") as f:
                data = tomllib.load(f)
            merged = {k: dict(v) for k, v in _DEFAULTS.items()}
            for section, values in data.items():
                merged.setdefault(section, {}).update(values)
            return merged
    return {k: dict(v) for k, v in _DEFAULTS.items()}


# ── server ───────────────────────────────────────────────────────────────────


def build_server(cfg: dict[str, Any]) -> FastMCP:
    srv = cfg["server"]
    models = cfg["models"]

    from openai_mcp.backend import BackendClient
    from openai_mcp.sse import ConversationClient

    _backend = BackendClient()
    conv = ConversationClient(_backend)

    mcp = FastMCP(
        "openai-mcp",
        host=str(srv.get("host", "0.0.0.0")),
        port=int(srv.get("port", 9000)),
        log_level="WARNING",
    )

    chat_model = models.get("chat", "gpt-5-3")

    @mcp.tool()
    async def chat(prompt: str, model: str = chat_model) -> str:
        """Chat with an AI model. Pass a different `model` name to switch models."""
        return await conv.complete(model, [{"role": "user", "content": prompt}])

    @mcp.tool()
    async def deep_research(query: str) -> str:
        """Search the web and synthesize a detailed report with citations.

        Best for: current events, literature review, market research.
        Takes 30–120 seconds. Uses model='research' + system_hints=['research'].
        """
        final_text = ""
        tool_calls: list[str] = []
        refs: list = []
        groups: list = []

        async for event in conv.deep_research(query):
            if event["type"] == "tool":
                tool_calls.append(event["call"])
            elif event["type"] == "done":
                final_text = event["text"]
                refs = event.get("content_references", [])
                groups = event.get("search_result_groups", [])

        # Append a brief sources section if citations were returned
        if refs:
            lines = ["\n\n---\n**Sources:**"]
            seen: set[str] = set()
            for ref in refs:
                for item in ref.get("items", []):
                    url = item.get("url", "")
                    title = item.get("title", url)
                    if url and url not in seen:
                        seen.add(url)
                        lines.append(f"- [{title}]({url})")
            final_text += "\n".join(lines)

        return final_text or "(no response)"

    # image_gen intentionally unregistered in 0.0.1 — the gpt-image-2 endpoint
    # is unverified in the native SSE build. Tracked for PR5. Re-add the
    # `@mcp.tool()` decorator once the endpoint is implemented and tested.
    async def image_gen(prompt: str) -> str:  # noqa: F841 (kept for PR5 wiring)
        """Placeholder for future gpt-image-2 support (not exposed as a tool)."""
        raise NotImplementedError(
            "image_gen not available in 0.0.1 — see PR5 for implementation"
        )

    try:
        from openai_mcp.tools import register_all

        register_all(mcp, _backend)
    except Exception as _exc:
        logging.getLogger(__name__).warning("backend tools unavailable: %s", _exc)

    return mcp


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="openai-mcp",
        description="Use your ChatGPT Plus/Pro in Claude Code and other AI agents.",
    )
    sub = parser.add_subparsers(dest="command")

    # setup subcommand
    sub.add_parser("setup", help="First-time setup wizard (login + register)")

    # run (default)
    run_p = sub.add_parser("run", help="Start the MCP server")
    run_p.add_argument("--config", type=Path, help="Path to config.toml")
    run_p.add_argument("--port", type=int)
    run_p.add_argument("--host")
    run_p.add_argument(
        "--stdio", action="store_true", help="stdio transport (Claude Code legacy)"
    )

    # bare flags for backward compat: openai-mcp --stdio --config ...
    parser.add_argument("--config", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--host")
    parser.add_argument("--stdio", action="store_true")

    args = parser.parse_args()

    if args.command == "setup":
        from openai_mcp.setup import run_setup

        run_setup()
        return

    # default: run server
    cfg_path = getattr(args, "config", None)
    cfg = load_config(cfg_path)
    if getattr(args, "port", None):
        cfg["server"]["port"] = args.port
    if getattr(args, "host", None):
        cfg["server"]["host"] = args.host

    mcp = build_server(cfg)
    tools = list(cfg["models"].keys())
    stdio = getattr(args, "stdio", False)

    if stdio:
        mcp.run(transport="stdio")
    else:
        host = cfg["server"]["host"]
        port = cfg["server"]["port"]
        print(f"openai-mcp  http://{host}:{port}/mcp  [{', '.join(tools)}]", flush=True)
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
