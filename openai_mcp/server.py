"""openai-mcp — MCP server for any OpenAI-compatible API."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from openai import AsyncOpenAI
from mcp.server.fastmcp import FastMCP

# ── config ──────────────────────────────────────────────────────────────────

_CONFIG_SEARCH = [
    Path.home() / ".openai-mcp" / "config.toml",
    Path("config.toml"),
    Path.home() / ".config" / "openai-mcp" / "config.toml",
]

_DEFAULTS: dict[str, Any] = {
    "api": {"base_url": "http://localhost:3001/v1", "api_key": "openai-mcp-local"},
    "server": {"host": "0.0.0.0", "port": 9000},
    "models": {"chat": "gpt-4o"},
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
    api = cfg["api"]
    srv = cfg["server"]
    models = cfg["models"]

    client = AsyncOpenAI(base_url=api["base_url"], api_key=api["api_key"])

    mcp = FastMCP(
        "openai-mcp",
        host=str(srv.get("host", "0.0.0.0")),
        port=int(srv.get("port", 9000)),
        log_level="WARNING",
    )

    chat_model = models.get("chat", "gpt-4o")

    @mcp.tool()
    async def chat(prompt: str, model: str = chat_model) -> str:
        """Chat with an AI model. Pass a different `model` name to switch models."""
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
        )
        return resp.choices[0].message.content or ""

    if "research" in models:
        research_model = models["research"]

        @mcp.tool()
        async def deep_research(query: str) -> str:
            """Search the web and synthesize a detailed report with citations.

            Best for: current events, literature review, market research.
            Takes 30–90 seconds.
            """
            resp = await client.chat.completions.create(
                model=research_model,
                messages=[{"role": "user", "content": query}],
                max_tokens=4000,
            )
            return resp.choices[0].message.content or ""

    if "image" in models:
        image_model = models["image"]

        @mcp.tool()
        async def image_gen(prompt: str) -> str:
            """Generate an image. Returns base64 PNG. Takes 60–120 seconds."""
            resp = await client.images.generate(
                model=image_model,
                prompt=prompt,
                response_format="b64_json",
                size="1024x1024",
            )
            return f"data:image/png;base64,{resp.data[0].b64_json}"

    try:
        from openai_mcp.backend import BackendClient
        from openai_mcp.tools import register_all

        register_all(mcp, BackendClient())
    except Exception as _exc:
        import logging

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
