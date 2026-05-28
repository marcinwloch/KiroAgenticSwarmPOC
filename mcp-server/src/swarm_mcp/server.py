"""MCP server entrypoint (stdio) — bridge Kiro to AgentCore Runtime."""

from __future__ import annotations

import argparse
import asyncio
import os

from mcp.server import Server
from mcp.server.stdio import stdio_server

from swarm_mcp.agentcore_client import AgentCoreClient, AgentCoreConfigError
from swarm_mcp.tools import register_tools
from swarm_mcp.handlers import register_handlers

server = Server("nortal-swarm")


async def run_stdio() -> None:
    """Run MCP server via stdio (Kiro integration)."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def self_test() -> int:
    """Smoke test: verify configuration and tool registration."""
    root_hint = os.environ.get("SWARM_WORKSPACE_ROOT", "(auto-detect)")
    endpoint = os.environ.get("SWARM_AGENTCORE_ENDPOINT", "")
    print("OK: nortal-swarm-mcp loaded, 8 tools registered")
    print(f"  workspace: {root_hint}")
    print(f"  agentcore: {endpoint or 'NOT SET'}")
    print(f"  sessions_table: {os.environ.get('SWARM_SESSIONS_TABLE', 'swarm-sessions')}")
    try:
        AgentCoreClient()
        print("  config: AgentCore client OK")
    except AgentCoreConfigError as exc:
        print(f"  config: {exc}")
        return 1
    return 0


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(prog="swarm_mcp.server")
    parser.add_argument("--self-test", action="store_true", help="Smoke test without stdio")
    args = parser.parse_args()

    # Register tools and handlers
    register_tools(server)
    register_handlers(server)

    if args.self_test:
        raise SystemExit(self_test())
    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
