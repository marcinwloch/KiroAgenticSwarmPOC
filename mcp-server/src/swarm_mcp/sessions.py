"""DynamoDB session helpers for MCP (seed + status)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import boto3
import structlog

log = structlog.get_logger()

STAGE_ORDER = ("architect", "developer", "tester", "reviewer")
NEXT_TOOL: dict[str, str | None] = {
    "seeded": "swarm.architect",
    "architect_done": "swarm.develop",
    "developer_done": "swarm.test",
    "tester_done": "swarm.review",
    "reviewer_done": None,
}


def _table_name() -> str:
    name = os.environ.get("SWARM_SESSIONS_TABLE", "swarm-sessions").strip()
    return name


def _client():
    region = os.environ.get("AWS_REGION", "eu-central-1")
    return boto3.client("dynamodb", region_name=region)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def create_session_id() -> str:
    return str(uuid.uuid4())


def seed_session(session_id: str, payload: dict[str, Any]) -> None:
    data = {
        "action": payload.get("action", "implement"),
        "spec_path": payload.get("spec_path", ""),
        "spec": payload.get("spec", ""),
        "steering": payload.get("steering") or {},
        "repo_path": payload.get("repo_path"),
        "repo": payload.get("repo") or {},
        "workspace_root": payload.get("workspace_root"),
        "stage_outputs": {},
        "judge_scores": {},
    }
    now = _now_iso()
    _client().put_item(
        TableName=_table_name(),
        Item={
            "sessionId": {"S": session_id},
            "status": {"S": "seeded"},
            "timestamp": {"S": now},
            "updated_at": {"S": now},
            "data": {"S": json.dumps(data, ensure_ascii=False)},
        },
    )
    log.info("mcp.session.seeded", session_id=session_id)


def get_session(session_id: str) -> dict[str, Any]:
    response = _client().get_item(
        TableName=_table_name(),
        Key={"sessionId": {"S": session_id}},
    )
    item = response.get("Item")
    if not item:
        raise KeyError(f"Session not found: {session_id}")
    data = json.loads(item.get("data", {}).get("S", "{}"))
    return {
        "session_id": session_id,
        "status": item.get("status", {}).get("S", "unknown"),
        "updated_at": item.get("updated_at", {}).get("S"),
        "runtime_session_id": item.get("runtime_session_id", {}).get("S"),
        "data": data,
    }


def update_runtime_session_id(session_id: str, runtime_session_id: str) -> None:
    session = get_session(session_id)
    now = _now_iso()
    item = {
        "sessionId": {"S": session_id},
        "status": {"S": session["status"]},
        "timestamp": {"S": session.get("updated_at") or now},
        "updated_at": {"S": now},
        "runtime_session_id": {"S": runtime_session_id},
        "data": {"S": json.dumps(session["data"], ensure_ascii=False)},
    }
    _client().put_item(TableName=_table_name(), Item=item)


def session_status(session_id: str) -> dict[str, Any]:
    try:
        session = get_session(session_id)
    except KeyError:
        return {"session_id": session_id, "found": False}

    status = session["status"]
    data = session["data"]
    stage_outputs = data.get("stage_outputs") or {}
    completed = [s for s in STAGE_ORDER if s in stage_outputs]

    next_tool = NEXT_TOOL.get(status, "swarm.architect")
    total = len(STAGE_ORDER)
    progress = f"{len(completed)} of {total} stages complete"
    if next_tool:
        for stage in STAGE_ORDER:
            if stage not in stage_outputs:
                idx = STAGE_ORDER.index(stage) + 1
                progress = f"stage {idx} of {total} — next: {stage}"
                break

    return {
        "session_id": session_id,
        "found": True,
        "status": status,
        "updated_at": session["updated_at"],
        "runtime_session_id": session.get("runtime_session_id"),
        "completed_stages": completed,
        "next_tool": next_tool,
        "next_args": {"session_id": session_id} if next_tool else {},
        "judge_scores": data.get("judge_scores") or {},
        "progress": progress,
        "spec_path": data.get("spec_path"),
    }
