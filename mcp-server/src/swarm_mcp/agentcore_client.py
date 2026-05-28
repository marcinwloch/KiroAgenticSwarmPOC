"""Thin wrapper around bedrock-agentcore InvokeAgentRuntime."""

from __future__ import annotations

import json
import os
from typing import Any

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

log = structlog.get_logger()

DEFAULT_INVOKE_TIMEOUT_SEC = 900
DEFAULT_STAGE_TIMEOUT_SEC = 300


class AgentCoreConfigError(ValueError):
    """Missing or invalid MCP / AgentCore configuration."""


class AgentCoreClient:
    def __init__(self) -> None:
        self.runtime_arn = os.environ.get("SWARM_AGENTCORE_ENDPOINT", "").strip()
        self.region = os.environ.get("AWS_REGION", "eu-central-1").strip()
        self.memory_arn = os.environ.get("SWARM_MEMORY_ARN", "").strip() or None
        self.gateway_url = os.environ.get("SWARM_GATEWAY_URL", "").strip() or None
        self.invoke_timeout_sec = int(
            os.environ.get("SWARM_INVOKE_TIMEOUT_SEC", DEFAULT_INVOKE_TIMEOUT_SEC)
        )
        self.stage_timeout_sec = int(
            os.environ.get("SWARM_STAGE_TIMEOUT_SEC", DEFAULT_STAGE_TIMEOUT_SEC)
        )
        if not self.runtime_arn:
            raise AgentCoreConfigError(
                "SWARM_AGENTCORE_ENDPOINT is not set. "
                "Add the AgentCore Runtime ARN from info.txt to .kiro/settings/mcp.json "
                "and reload MCP."
            )

    def invoke(
        self,
        payload: dict[str, Any],
        *,
        runtime_session_id: str | None = None,
    ) -> dict[str, Any]:
        stage = payload.get("stage")
        is_stage = stage in {"architect", "developer", "tester", "reviewer", "summary"}
        read_timeout = self.stage_timeout_sec if is_stage else self.invoke_timeout_sec

        config = Config(
            connect_timeout=60,
            read_timeout=read_timeout,
            retries={"max_attempts": 0},
        )
        client = boto3.client("bedrock-agentcore", region_name=self.region, config=config)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        invoke_kwargs: dict[str, Any] = {
            "agentRuntimeArn": self.runtime_arn,
            "contentType": "application/json",
            "accept": "application/json",
            "payload": body,
        }
        if runtime_session_id:
            invoke_kwargs["runtimeSessionId"] = runtime_session_id

        log.info(
            "agentcore.invoke",
            action=payload.get("action"),
            stage=stage,
            runtime_arn=self.runtime_arn,
            payload_bytes=len(body),
            read_timeout_sec=read_timeout,
            runtime_session_id=runtime_session_id,
        )

        try:
            response = client.invoke_agent_runtime(**invoke_kwargs)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "ClientError")
            message = exc.response.get("Error", {}).get("Message", str(exc))
            log.error("agentcore.client_error", code=code, message=message)
            raise RuntimeError(f"AgentCore invoke failed ({code}): {message}") from exc
        except BotoCoreError as exc:
            log.error("agentcore.boto_error", error=str(exc))
            if "Read timeout" in str(exc):
                hint = (
                    "Use stage tools (swarm.start → swarm.architect → …) for live progress, "
                    "or raise SWARM_STAGE_TIMEOUT_SEC / SWARM_INVOKE_TIMEOUT_SEC in mcp.json."
                )
                raise RuntimeError(
                    f"AgentCore invoke timed out after {read_timeout}s. {hint} "
                    "Check CloudWatch log group /aws/agentcore/swarm."
                ) from exc
            raise RuntimeError(f"AgentCore invoke failed: {exc}") from exc

        status = response.get("statusCode", 0)
        stream = response.get("response")
        raw = stream.read().decode("utf-8") if hasattr(stream, "read") else ""
        parsed: Any
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}

        result = {
            "statusCode": status,
            "runtimeSessionId": response.get("runtimeSessionId"),
            "traceId": response.get("traceId"),
            "body": parsed,
        }
        if status >= 400:
            raise RuntimeError(
                f"AgentCore runtime returned HTTP {status}: "
                f"{json.dumps(parsed, ensure_ascii=False)[:500]}"
            )
        return result
