from __future__ import annotations

from agents.judges.base_judge import evaluate
from agents.schemas import JudgeVerdict, TaskContext, WorkerResult

RUBRIC = """
- Aligns with AWS Well-Architected (security, reliability, ops, performance, cost).
- Respects steering constitution (layering, 12-factor config, scope).
- Plan is actionable and covers spec requirements without hand-waving.
"""


def judge(ctx: TaskContext, result: WorkerResult) -> JudgeVerdict:
    return evaluate("architect", RUBRIC, ctx, result)
