#!/usr/bin/env python3
"""Verify the selected Python's installed package, never the caller's checkout.

Run with ``<target-python> -I scripts/verify_install.py --version X.Y.Z``.
The optional wheel check compares package bytes; MCP smoke uses an isolated,
unauthenticated home and a manual handoff, so it sends no conversation.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def verify_files(package: Path, wheel: Path) -> int:
    count = 0
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if not name.startswith("gpt2agent/") or name.endswith("/"):
                continue
            relative = Path(name).relative_to("gpt2agent")
            if ".." in relative.parts:
                raise ValueError("wheel contains an unsafe package path")
            if (package / relative).read_bytes() != archive.read(name):
                raise ValueError(f"installed file differs from wheel: {relative}")
            count += 1
    if not count:
        raise ValueError("wheel contains no gpt2agent files")
    return count


async def mcp_smoke(home: Path) -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    required = {"chat", "agent", "deep_research", "deep_research_heavy", "gpt_chat",
                "memory_create_via_chat", "generate_image", "code_interpreter", "canvas_execute"}
    # Startup requires a credential even for manual handoff. Supply an invalid
    # in-memory fixture and block HTTP; never read/copy a device's real token.
    bootstrap = """
from curl_cffi import requests
from gpt2agent import backend
from gpt2agent.server import main
def deny(*args, **kwargs):
    raise RuntimeError("network disabled during installation verification")
requests.Session.request = deny
requests.AsyncSession.request = deny
backend._load_token_with_source = lambda: ("offline-install-verification", None)
main()
"""
    params = StdioServerParameters(
        command=sys.executable, args=["-I", "-c", bootstrap, "run", "--stdio"],
        cwd=str(home), env={"HOME": str(home), "USERPROFILE": str(home),
                           "CODEX_HOME": str(home / ".codex"),
                           "GPT2AGENT_SENTINEL_BRIDGE_OFF": "1"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            if len(tools) < 30 or not required <= tools.keys():
                raise ValueError("installed MCP tool catalog is incomplete")
            for name in required:
                schema = tools[name].inputSchema
                if "manual" not in schema.get("properties", {}) or "manual" in schema.get(
                    "required", []
                ):
                    raise ValueError(f"invalid manual handoff schema: {name}")
            result = await session.call_tool("chat", {"prompt": "install verification", "manual": True})
            handoff = json.loads(result.content[0].text) if result.content and not result.isError else {}
            if handoff.get("status") != "manual_handoff":
                raise ValueError("installed MCP manual handoff failed")
    return {"tools": len(tools), "manual_schemas": len(required), "manual_handoff": "pass"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--root", type=Path, help="expected imported package directory")
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--mcp", action="store_true")
    args = parser.parse_args()
    if not sys.flags.isolated:
        parser.error("use the target Python with -I to exclude checkout/PYTHONPATH shadowing")
    import gpt2agent

    package = Path(gpt2agent.__file__).resolve().parent
    metadata = importlib.metadata.version("gpt2agent")
    if gpt2agent.__version__ != args.version or metadata != args.version:
        raise ValueError(f"version mismatch: code={gpt2agent.__version__}, metadata={metadata}, "
                         f"expected={args.version}")
    if args.root and package != args.root.resolve():
        raise ValueError(f"wrong imported package: {package}")
    result = {"python": sys.executable, "version": args.version, "metadata": metadata,
              "module": str(package)}
    if args.wheel:
        result["verified_files"] = verify_files(package, args.wheel)
    # No token, source checkout, or user configuration is needed for these checks.
    with tempfile.TemporaryDirectory(prefix="gpt2agent-verify-") as directory:
        home = Path(directory)
        cli = subprocess.run([sys.executable, "-I", "-m", "gpt2agent", "--version"],
                             cwd=home, capture_output=True, text=True, timeout=30, check=True)
        if cli.stdout.strip() != f"gpt2agent {args.version}":
            raise ValueError("installed CLI reports a different version")
        if args.mcp:
            result["mcp"] = asyncio.run(asyncio.wait_for(mcp_smoke(home), timeout=45))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"installation verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
