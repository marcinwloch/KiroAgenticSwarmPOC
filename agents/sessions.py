"""DynamoDB session store for stage-based swarm pipeline."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

import boto3
import structlog

log = structlog.get_logger()

STAGE_ORDER = ("architect", "developer", "tester", "reviewer")
NEXT_STAGE: dict[str, str | None] = {
    "architect": "developer",
    "developer": "tester",
    "tester": "reviewer",
    "reviewer": None,
}
NEXT_TOOL: dict[str, str | None] = {
    "architect": "swarm.develop",
    "developer": "swarm.test",
    "tester": "swarm.review",
    "reviewer": None,
}


def _table_name() -> str:
    name = os.environ.get("SWARM_SESSIONS_TABLE", "").strip()
    if not name:
        raise RuntimeError("SWARM_SESSIONS_TABLE is not configured")
    return name


def _client():
    region = os.environ.get("AWS_REGION", "eu-central-1")
    return boto3.client("dynamodb", region_name=region)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _serialize_data(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def _deserialize_data(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    return json.loads(raw)


def load_session(session_id: str) -> dict[str, Any]:
    response = _client().get_item(
        TableName=_table_name(),
        Key={"sessionId": {"S": session_id}},
    )
    item = response.get("Item")
    if not item:
        raise KeyError(f"Session not found: {session_id}")
    data = _deserialize_data(item.get("data", {}).get("S"))
    return {
        "session_id": session_id,
        "status": item.get("status", {}).get("S", "unknown"),
        "timestamp": item.get("timestamp", {}).get("S"),
        "updated_at": item.get("updated_at", {}).get("S"),
        "runtime_session_id": item.get("runtime_session_id", {}).get("S"),
        "data": data,
    }


def save_seed(session_id: str, seed_payload: dict[str, Any]) -> None:
    data = {
        "action": seed_payload.get("action", "implement"),
        "spec_path": seed_payload.get("spec_path", ""),
        "spec": seed_payload.get("spec", ""),
        "steering": seed_payload.get("steering") or {},
        "repo_path": seed_payload.get("repo_path"),
        "repo": seed_payload.get("repo") or {},
        "workspace_root": seed_payload.get("workspace_root"),
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
            "data": {"S": _serialize_data(data)},
        },
    )
    log.info("session.seeded", session_id=session_id)


def save_stage(
    session_id: str,
    stage: str,
    result: dict[str, Any],
    *,
    runtime_session_id: str | None = None,
) -> None:
    session = load_session(session_id)
    data = session["data"]
    stage_outputs: dict[str, Any] = data.setdefault("stage_outputs", {})
    stage_outputs[stage] = result

    verdict = result.get("verdict") or {}
    if verdict.get("score") is not None:
        data.setdefault("judge_scores", {})[stage] = verdict["score"]

    status = f"{stage}_done" if stage in STAGE_ORDER else stage
    now = _now_iso()

    item: dict[str, Any] = {
        "sessionId": {"S": session_id},
        "status": {"S": status},
        "timestamp": {"S": session.get("timestamp") or now},
        "updated_at": {"S": now},
        "data": {"S": _serialize_data(data)},
    }
    if runtime_session_id:
        item["runtime_session_id"] = {"S": runtime_session_id}

    _client().put_item(TableName=_table_name(), Item=item)
    log.info("session.stage_saved", session_id=session_id, stage=stage, status=status)


def session_status(session_id: str) -> dict[str, Any]:
    try:
        session = load_session(session_id)
    except KeyError:
        return {"session_id": session_id, "found": False}

    data = session["data"]
    stage_outputs = data.get("stage_outputs") or {}
    completed = [s for s in STAGE_ORDER if s in stage_outputs]
    current = NEXT_STAGE.get(completed[-1]) if completed else "architect"
    if completed and completed[-1] == "reviewer":
        current = None

    total = len(STAGE_ORDER)
    progress = f"{len(completed)} of {total} stages complete"
    if current:
        idx = STAGE_ORDER.index(current) + 1
        progress = f"stage {idx} of {total} — next: {current}"

    return {
        "session_id": session_id,
        "found": True,
        "status": session["status"],
        "updated_at": session["updated_at"],
        "runtime_session_id": session.get("runtime_session_id"),
        "completed_stages": completed,
        "next_stage": current,
        "next_tool": NEXT_TOOL.get(completed[-1]) if completed else "swarm.architect",
        "judge_scores": data.get("judge_scores") or {},
        "progress": progress,
        "spec_path": data.get("spec_path"),
    }


def update_runtime_session_id(session_id: str, runtime_session_id: str) -> None:
    session = load_session(session_id)
    now = _now_iso()
    _client().put_item(
        TableName=_table_name(),
        Item={
            "sessionId": {"S": session_id},
            "status": {"S": session["status"]},
            "timestamp": {"S": session.get("timestamp") or now},
            "updated_at": {"S": now},
            "runtime_session_id": {"S": runtime_session_id},
            "data": {"S": _serialize_data(session["data"])},
        },
    )


def build_summary(session_id: str) -> dict[str, Any]:
    session = load_session(session_id)
    data = session["data"]
    stage_outputs = data.get("stage_outputs") or {}

    proposed_files: dict[str, str] = {}
    for stage in ("developer", "tester"):
        out = stage_outputs.get(stage) or {}
        proposed_files.update(out.get("files") or {})

    return {
        "session_id": session_id,
        "status": session["status"],
        "judge_scores": data.get("judge_scores") or {},
        "proposed_files": proposed_files,
        "stage_outputs": {
            k: {"output": v.get("output", "")[:500], "files": list((v.get("files") or {}).keys())}
            for k, v in stage_outputs.items()
        },
        "progress": session_status(session_id)["progress"],
    }
