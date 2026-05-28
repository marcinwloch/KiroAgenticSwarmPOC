from __future__ import annotations

from collections.abc import Callable

import structlog

from agents.schemas import JudgeVerdict, TaskContext, WorkerResult

log = structlog.get_logger()


def run_worker_with_judge(
    agent_name: str,
    worker: Callable[[TaskContext], WorkerResult],
    judge: Callable[[TaskContext, WorkerResult], JudgeVerdict],
    task: TaskContext,
    *,
    max_retries: int = 3,
) -> WorkerResult:
    feedback: list[str] = []
    last: WorkerResult | None = None

    for attempt in range(1, max_retries + 1):
        attempt_ctx = task.model_copy(update={"feedback": feedback})
        result = worker(attempt_ctx)
        result.attempts = attempt
        verdict = judge(attempt_ctx, result)
        result.verdict = verdict
        last = result

        log.info(
            "worker.judge",
            agent=agent_name,
            attempt=attempt,
            score=verdict.score,
            passed=verdict.passed,
        )

        if verdict.passed:
            return result

        feedback = verdict.required_fixes or verdict.reasons
        if not feedback:
            feedback = ["Improve output quality to meet spec and constitution."]

    assert last is not None
    return last
