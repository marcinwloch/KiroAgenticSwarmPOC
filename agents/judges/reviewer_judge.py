from __future__ import annotations

from agents.judges.base_judge import evaluate
from agents.schemas import JudgeVerdict, TaskContext, WorkerResult

RUBRIC = """
- At least 3 actionable findings tied to spec/constitution OR clear approval with evidence.
- Findings must be substantive, not style-only nitpicks.
- LGTM without evidence = fail.
"""


def judge(ctx: TaskContext, result: WorkerResult) -> JudgeVerdict:
    return evaluate("reviewer", RUBRIC, ctx, result)
