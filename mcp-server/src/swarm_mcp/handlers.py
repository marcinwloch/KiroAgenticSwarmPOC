"""Tool handlers for nortal-swarm MCP server."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from mcp.server import Server
from mcp.types import TextContent

from swarm_mcp.agentcore_client import AgentCoreClient, AgentCoreConfigError
from swarm_mcp.context import build_payload
from swarm_mcp import sessions as mcp_sessions
from swarm_mcp.tools import SESSION_ID_SCHEMA, SPEC_REPO_SCHEMA

log = structlog.get_logger()


def _format_result(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def _merge_invoke_result(invoke_result: dict) -> dict:
    body = invoke_result.get("body") or {}
    return {
        "statusCode": invoke_result.get("statusCode"),
        "runtimeSessionId": invoke_result.get("runtimeSessionId"),
        "traceId": invoke_result.get("traceId"),
        **body,
    }


async def _invoke_stage(
    client: AgentCoreClient,
    session_id: str,
    stage: str,
) -> dict:
    session = mcp_sessions.get_session(session_id)
    payload = {
        "session_id": session_id,
        "stage": stage,
        "action": session["data"].get("action", "implement"),
        "runtime_session_id": session.get("runtime_session_id"),
    }
    runtime_session_id = session.get("runtime_session_id")
    invoke_result = await asyncio.to_thread(
        client.invoke, payload, runtime_session_id=runtime_session_id
    )
    merged = _merge_invoke_result(invoke_result)
    new_runtime_session = invoke_result.get("runtimeSessionId")
    if new_runtime_session:
        mcp_sessions.update_runtime_session_id(session_id, new_runtime_session)
        merged["runtimeSessionId"] = new_runtime_session
    return merged


async def _handle_start(arguments: dict) -> list[TextContent]:
    """Handle swarm.start tool call."""
    spec_path = arguments.get("spec_path", "")
    repo_path = arguments.get("repo_path")
    if not repo_path:
        raise ValueError("swarm.start requires repo_path")
    payload = build_payload("implement", spec_path, repo_path)
    session_id = mcp_sessions.create_session_id()
    mcp_sessions.seed_session(session_id, payload)
    spec_preview = payload["spec"][:400].replace("\n", " ")
    result = {
        "session_id": session_id,
        "status": "seeded",
        "spec_path": spec_path,
        "repo_path": repo_path,
        "spec_summary": spec_preview + ("..." if len(payload["spec"]) > 400 else ""),
        "next_tool": "swarm.architect",
        "next_args": {"session_id": session_id},
        "message": f"Session {session_id} created. Now run swarm.architect with session_id={session_id}.",
        "progress": "stage 1 of 4 — next: architect",
    }
    return [TextContent(type="text", text=_format_result(result))]


async def _handle_status(arguments: dict) -> list[TextContent]:
    """Handle swarm.status tool call."""
    session_id = arguments.get("session_id", "")
    if not session_id:
        raise ValueError("swarm.status requires session_id")
    result = mcp_sessions.session_status(session_id)
    if result.get("found"):
        nt = result.get("next_tool")
        result["message"] = (
            f"Progress: {result.get('progress')}. "
            + (f"Run {nt} with session_id={session_id}." if nt else "All stages complete.")
        )
    return [TextContent(type="text", text=_format_result(result))]


async def _handle_stage(
    client: AgentCoreClient,
    name: str,
    arguments: dict,
    stage_map: dict[str, str],
) -> list[TextContent]:
    """Handle swarm.architect/develop/test tool calls."""
    session_id = arguments.get("session_id", "")
    if not session_id:
        raise ValueError(f"{name} requires session_id")
    try:
        merged = await _invoke_stage(client, session_id, stage_map[name])
    except KeyError as exc:
        raise RuntimeError(str(exc)) from exc
    return [TextContent(type="text", text=_format_result(merged))]


async def _handle_review(
    client: AgentCoreClient,
    arguments: dict,
) -> list[TextContent]:
    """Handle swarm.review tool call (staged or legacy single-shot)."""
    session_id = arguments.get("session_id", "")
    if session_id:
        try:
            merged = await _invoke_stage(client, session_id, "reviewer")
        except KeyError as exc:
            raise RuntimeError(str(exc)) from exc
        return [TextContent(type="text", text=_format_result(merged))]
    spec_path = arguments.get("spec_path", "")
    repo_path = arguments.get("repo_path")
    if not spec_path or not repo_path:
        raise ValueError("swarm.review requires session_id OR spec_path+repo_path")
    payload = build_payload("review", spec_path, repo_path)
    payload["stage"] = "full"
    invoke_result = await asyncio.to_thread(client.invoke, payload)
    merged = _merge_invoke_result(invoke_result)
    return [TextContent(type="text", text=_format_result(merged))]


async def _handle_legacy_action(
    client: AgentCoreClient,
    name: str,
    arguments: dict,
) -> list[TextContent]:
    """Handle swarm.plan and swarm.implement tool calls (legacy single-shot)."""
    action = name.removeprefix("swarm.")
    spec_path = arguments.get("spec_path", "")
    repo_path = arguments.get("repo_path")

    if action == "implement" and not repo_path:
        raise ValueError(f"{name} requires repo_path")

    try:
        payload = build_payload(action, spec_path, repo_path)
        payload["stage"] = "full"
        invoke_result = await asyncio.to_thread(client.invoke, payload)
        merged = _merge_invoke_result(invoke_result)
    except FileNotFoundError as exc:
        raise RuntimeError(str(exc)) from exc

    log.info(
        "tool.complete",
        tool=name,
        status=merged.get("statusCode"),
        session=merged.get("runtimeSessionId") or merged.get("session_id"),
    )
    return [TextContent(type="text", text=_format_result(merged))]


def register_handlers(server: Server) -> None:
    """Register call_tool handler with the MCP server."""

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            client = AgentCoreClient()
        except AgentCoreConfigError as exc:
            raise RuntimeError(str(exc)) from exc

        if name == "swarm.start":
            return await _handle_start(arguments)

        if name == "swarm.status":
            return await _handle_status(arguments)

        stage_map = {
            "swarm.architect": "architect",
            "swarm.develop": "developer",
            "swarm.test": "tester",
        }
        if name in stage_map:
            return await _handle_stage(client, name, arguments, stage_map)

        if name == "swarm.review":
            return await _handle_review(client, arguments)

        # Legacy single-shot actions
        return await _handle_legacy_action(client, name, arguments)
