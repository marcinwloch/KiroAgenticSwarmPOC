from __future__ import annotations

import time
import uuid
from typing import Any

import structlog

from agents.judges import architect_judge, developer_judge, reviewer_judge, tester_judge
from agents.schemas import SwarmReport, TaskContext, WorkerResult
from agents import sessions as session_store
from agents.specialists import architect, developer, reviewer, tester
from agents.worker_loop import run_worker_with_judge

log = structlog.get_logger()

_STAGE_RUNNERS = {
    "architect": (architect.run, architect_judge.judge),
    "developer": (developer.run, developer_judge.judge),
    "tester": (tester.run, tester_judge.judge),
    "reviewer": (reviewer.run, reviewer_judge.judge),
}


def _parse_payload(payload: dict[str, Any]) -> TaskContext:
    repo = payload.get("repo") or {}
    return TaskContext(
        action=str(payload.get("action", "implement")),
        spec_path=str(payload.get("spec_path", "")),
        spec=str(payload.get("spec", "")),
        steering=dict(payload.get("steering") or {}),
        repo_path=payload.get("repo_path"),
        repo_files=list(repo.get("files") or []),
        repo_contents=dict(repo.get("contents") or {}),
    )


def _ctx_from_session_data(data: dict[str, Any]) -> TaskContext:
    repo = data.get("repo") or {}
    ctx = TaskContext(
        action=str(data.get("action", "implement")),
        spec_path=str(data.get("spec_path", "")),
        spec=str(data.get("spec", "")),
        steering=dict(data.get("steering") or {}),
        repo_path=data.get("repo_path"),
        repo_files=list(repo.get("files") or []),
        repo_contents=dict(repo.get("contents") or {}),
    )
    _apply_prior_from_stages(ctx, data.get("stage_outputs") or {})
    return ctx


def _apply_prior_from_stages(ctx: TaskContext, stage_outputs: dict[str, Any]) -> None:
    arch = stage_outputs.get("architect") or {}
    dev = stage_outputs.get("developer") or {}
    test = stage_outputs.get("tester") or {}
    ctx.prior = {
        "architect_output": arch.get("output", ""),
        "developer_output": dev.get("output", ""),
        "developer_files": dev.get("files") or {},
        "tester_output": test.get("output", ""),
    }


def _worker_to_dict(result: WorkerResult) -> dict[str, Any]:
    return {
        "agent": result.agent,
        "output": result.output,
        "files": result.files,
        "attempts": result.attempts,
        "verdict": result.verdict.model_dump(mode="json") if result.verdict else None,
    }


def _merge_files(*results: WorkerResult | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for item in results:
        if item and item.files:
            merged.update(item.files)
    return merged


def _scores(report: SwarmReport) -> dict[str, int]:
    scores: dict[str, int] = {}
    for name in ("architect", "developer", "tester", "reviewer"):
        worker: WorkerResult | None = getattr(report, name)
        if worker and worker.verdict:
            scores[name] = worker.verdict.score
    return scores


def _stage_progress(stage: str) -> str:
    if stage not in session_store.STAGE_ORDER:
        return stage
    idx = session_store.STAGE_ORDER.index(stage) + 1
    return f"stage {idx} of {len(session_store.STAGE_ORDER)} — {stage}"


def _stage_response(
    session_id: str,
    stage: str,
    result: WorkerResult,
    *,
    duration_s: float,
    runtime_session_id: str | None = None,
) -> dict[str, Any]:
    next_stage = session_store.NEXT_STAGE.get(stage)
    next_tool = session_store.NEXT_TOOL.get(stage)
    next_args = {"session_id": session_id} if next_tool else {}
    passed = bool(result.verdict and result.verdict.passed)
    output = result.output or ""
    guardrail_blocked = "GUARDRAIL_BLOCKED" in output
    bedrock_error = output.startswith("BEDROCK_ERROR:")

    if guardrail_blocked or bedrock_error:
        status = "error"
        message = (
            f"Stage '{stage}' failed: {output[:300]}. "
            "Do NOT implement locally in Kiro — fix runtime and retry the same MCP tool."
        )
        next_tool = None
        next_args = {}
    elif passed:
        status = "ok"
        message = (
            f"Stage '{stage}' complete. Now run {next_tool} with session_id={session_id}."
            if next_tool
            else f"All stages complete for session {session_id}. Run swarm.status for summary."
        )
    else:
        status = "error"
        fixes = (result.verdict.required_fixes if result.verdict else []) or []
        hint = fixes[0] if fixes else "Judge did not pass."
        message = (
            f"Stage '{stage}' failed ({hint}). "
            "Do NOT implement locally — retry the same MCP stage or run swarm.status."
        )
        next_tool = None
        next_args = {}

    return {
        "status": status,
        "session_id": session_id,
        "stage": stage,
        "output": result.output,
        "files": result.files,
        "verdict": result.verdict.model_dump(mode="json") if result.verdict else None,
        "attempts": result.attempts,
        "next_stage": next_stage if passed else None,
        "next_tool": next_tool,
        "next_args": next_args,
        "message": message,
        "progress": _stage_progress(stage),
        "duration_s": round(duration_s, 2),
        "runtime_session_id": runtime_session_id,
        "guardrail_blocked": guardrail_blocked,
    }


def run_stage_architect(ctx: TaskContext) -> WorkerResult:
    return run_worker_with_judge(
        "architect", architect.run, architect_judge.judge, ctx, max_retries=2
    )


def run_stage_developer(ctx: TaskContext) -> WorkerResult:
    return run_worker_with_judge(
        "developer", developer.run, developer_judge.judge, ctx, max_retries=2
    )


def run_stage_tester(ctx: TaskContext) -> WorkerResult:
    return run_worker_with_judge("tester", tester.run, tester_judge.judge, ctx, max_retries=2)


def run_stage_reviewer(ctx: TaskContext) -> WorkerResult:
    return run_worker_with_judge(
        "reviewer", reviewer.run, reviewer_judge.judge, ctx, max_retries=2
    )


def run_stage(payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    session_id = str(payload.get("session_id", ""))
    stage = str(payload.get("stage", ""))

    if not session_id or stage not in _STAGE_RUNNERS:
        raise ValueError(f"Invalid stage request: session_id={session_id!r}, stage={stage!r}")

    session = session_store.load_session(session_id)
    ctx = _ctx_from_session_data(session["data"])
    worker_fn, judge_fn = _STAGE_RUNNERS[stage]

    log.info("stage.start", session_id=session_id, stage=stage)
    result = run_worker_with_judge(stage, worker_fn, judge_fn, ctx, max_retries=2)
    result_dict = _worker_to_dict(result)

    runtime_session_id = payload.get("runtime_session_id")
    session_store.save_stage(
        session_id,
        stage,
        result_dict,
        runtime_session_id=runtime_session_id,
    )

    duration_s = time.perf_counter() - started
    response = _stage_response(session_id, stage, result, duration_s=duration_s, runtime_session_id=runtime_session_id)
    if runtime_session_id:
        response["runtime_session_id"] = runtime_session_id
    response["judge_scores"] = session_store.load_session(session_id)["data"].get("judge_scores") or {}
    log.info("stage.done", session_id=session_id, stage=stage, duration_s=duration_s)
    return response


def run_summary(payload: dict[str, Any]) -> dict[str, Any]:
    session_id = str(payload.get("session_id", ""))
    if not session_id:
        raise ValueError("session_id is required for summary stage")
    summary = session_store.build_summary(session_id)
    summary["next_tool"] = None
    summary["message"] = f"Summary for session {session_id}."
    return summary


def run_swarm(payload: dict[str, Any]) -> SwarmReport:
    """Full pipeline (legacy swarm.implement)."""
    started = time.perf_counter()
    session_id = str(payload.get("session_id") or uuid.uuid4())
    ctx = _parse_payload(payload)
    action = ctx.action

    log.info("swarm.start", session_id=session_id, action=action, spec=ctx.spec_path)

    report = SwarmReport(action=action, session_id=session_id)

    try:
        if action == "plan":
            report.architect = run_stage_architect(ctx)
        elif action == "review":
            ctx.prior = {
                "architect_output": "(skipped in review-only run)",
                "developer_output": "(see repo snapshot)",
                "tester_output": "(see repo snapshot)",
            }
            report.reviewer = run_stage_reviewer(ctx)
        else:
            report.architect = run_stage_architect(ctx)
            ctx.prior["architect_output"] = report.architect.output

            report.developer = run_stage_developer(ctx)
            ctx.prior["developer_output"] = report.developer.output
            ctx.prior["developer_files"] = report.developer.files

            report.tester = run_stage_tester(ctx)
            ctx.prior["tester_output"] = report.tester.output

            report.reviewer = run_stage_reviewer(ctx)

        report.proposed_files = _merge_files(report.developer, report.tester)
        report.judge_scores = _scores(report)
        report.duration_s = round(time.perf_counter() - started, 2)

        failed = [
            name
            for name, worker in (
                ("architect", report.architect),
                ("developer", report.developer),
                ("tester", report.tester),
                ("reviewer", report.reviewer),
            )
            if worker and worker.verdict and not worker.verdict.passed
        ]
        if failed:
            report.status = "partial"
            report.notes.append(f"Judge did not pass for: {', '.join(failed)}")

    except Exception as exc:
        log.exception("swarm.error", session_id=session_id)
        report.status = "error"
        report.notes.append(str(exc))
        report.duration_s = round(time.perf_counter() - started, 2)

    log.info(
        "swarm.done",
        session_id=session_id,
        status=report.status,
        duration_s=report.duration_s,
        files=len(report.proposed_files),
    )
    return report
