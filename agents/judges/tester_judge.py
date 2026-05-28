from __future__ import annotations

from agents.judges.base_judge import evaluate
from agents.schemas import JudgeVerdict, TaskContext, WorkerResult

RUBRIC = """
- Each major acceptance criterion has a corresponding test.
- Tests use httpx AsyncClient pattern; not tautological (would fail if code removed).
- AAA structure; fixtures over copy-paste.
"""


def judge(ctx: TaskContext, result: WorkerResult) -> JudgeVerdict:
    verdict = evaluate("tester", RUBRIC, ctx, result)
    if ctx.action == "implement" and not result.files:
        verdict.passed = False
        verdict.score = min(verdict.score, 50)
        verdict.required_fixes.append("Add pytest files covering acceptance criteria.")
    return verdict
