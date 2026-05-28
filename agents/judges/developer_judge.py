from __future__ import annotations

from agents.judges.base_judge import evaluate
from agents.schemas import JudgeVerdict, TaskContext, WorkerResult

RUBRIC = """
- Implements spec requirements with minimal scope.
- SOLID/DDD-light: routers -> services -> db, no secrets hardcoded.
- Files are syntactically plausible Python/FastAPI; includes needed dependencies hints.
- passed=false if no files returned when implementation was required.
"""


def judge(ctx: TaskContext, result: WorkerResult) -> JudgeVerdict:
    verdict = evaluate("developer", RUBRIC, ctx, result)
    if ctx.action == "implement" and not result.files:
        verdict.passed = False
        verdict.score = min(verdict.score, 40)
        verdict.required_fixes.append("Return at least one file with full content in structured output.")
    return verdict
