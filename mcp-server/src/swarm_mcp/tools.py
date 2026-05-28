"""Tool definitions for nortal-swarm MCP server."""

from mcp.server import Server
from mcp.types import Tool

# Input schemas for tools
SESSION_ID_SCHEMA = {
    "type": "object",
    "properties": {"session_id": {"type": "string"}},
    "required": ["session_id"],
}

SPEC_REPO_SCHEMA = {
    "type": "object",
    "properties": {
        "spec_path": {"type": "string"},
        "repo_path": {"type": "string"},
    },
    "required": ["spec_path", "repo_path"],
}


def register_tools(server: Server) -> None:
    """Register all swarm tools with the MCP server."""

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="swarm.start",
                description=(
                    "Start a staged swarm session (~1s). Seeds spec+repo to DynamoDB. "
                    "Returns session_id and next_tool=swarm.architect. Prefer over swarm.implement for live UX."
                ),
                inputSchema=SPEC_REPO_SCHEMA,
            ),
            Tool(
                name="swarm.architect",
                description="Run architect stage (~1-3 min). Requires session_id from swarm.start.",
                inputSchema=SESSION_ID_SCHEMA,
            ),
            Tool(
                name="swarm.develop",
                description="Run developer stage (~2-4 min). Requires session_id after swarm.architect.",
                inputSchema=SESSION_ID_SCHEMA,
            ),
            Tool(
                name="swarm.test",
                description="Run tester stage (~1-3 min). Requires session_id after swarm.develop.",
                inputSchema=SESSION_ID_SCHEMA,
            ),
            Tool(
                name="swarm.review",
                description=(
                    "Reviewer stage (~1-2 min) when session_id is provided (after swarm.test). "
                    "Legacy single-shot review when spec_path+repo_path are provided instead."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "spec_path": {"type": "string"},
                        "repo_path": {"type": "string"},
                    },
                },
            ),
            Tool(
                name="swarm.status",
                description="Read session progress from DynamoDB (~1s). Use to resume or diagnose.",
                inputSchema=SESSION_ID_SCHEMA,
            ),
            Tool(
                name="swarm.plan",
                description="Plan implementation from a .kiro/specs/*.md file via AgentCore (single shot).",
                inputSchema={
                    "type": "object",
                    "properties": {"spec_path": {"type": "string"}},
                    "required": ["spec_path"],
                },
            ),
            Tool(
                name="swarm.implement",
                description=(
                    "Run FULL swarm in one call (~10 min, blocks until done). "
                    "Prefer swarm.start + stage tools for live progress in chat."
                ),
                inputSchema=SPEC_REPO_SCHEMA,
            ),
        ]
