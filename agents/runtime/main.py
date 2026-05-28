"""AgentCore Runtime — FastAPI host for Nortal swarm supervisor."""

from __future__ import annotations

import json
import os
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agents.supervisor import run_stage, run_summary, run_swarm

structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()

app = FastAPI(title="nortal-swarm-runtime", version="0.3.0")


def _envelope(body: dict[str, Any]) -> dict[str, Any]:
    body["region"] = os.environ.get("AWS_REGION", "unknown")
    body["artifacts_bucket"] = os.environ.get("SWARM_ARTIFACTS_BUCKET")
    body["sessions_table"] = os.environ.get("SWARM_SESSIONS_TABLE")
    return body


@app.get("/ping")
def ping() -> dict[str, str]:
    return {"status": "Healthy"}


@app.post("/invocations")
async def invocations(request: Request) -> JSONResponse:
    raw = await request.body()
    payload: dict[str, Any] = {}
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "detail": "Invalid JSON body"},
            )

    stage = payload.get("stage", "full")
    log.info(
        "invocation.received",
        action=payload.get("action"),
        stage=stage,
        session_id=payload.get("session_id"),
        spec_path=payload.get("spec_path"),
    )

    try:
        if stage == "summary":
            body = _envelope(run_summary(payload))
        elif stage in {"architect", "developer", "tester", "reviewer"}:
            body = _envelope(run_stage(payload))
        else:
            report = run_swarm(payload)
            body = _envelope(report.model_dump(mode="json"))
        return JSONResponse(body)
    except KeyError as exc:
        log.exception("invocation.not_found")
        return JSONResponse(status_code=404, content={"status": "error", "detail": str(exc)})
    except ValueError as exc:
        log.exception("invocation.bad_request")
        return JSONResponse(status_code=400, content={"status": "error", "detail": str(exc)})
    except Exception as exc:
        log.exception("invocation.failed")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(exc)},
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
