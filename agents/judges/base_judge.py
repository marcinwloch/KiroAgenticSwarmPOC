from __future__ import annotations

from agents.models import make_agent
from agents.schemas import JudgeVerdict, TaskContext, WorkerResult

JUDGE_SYSTEM = """You are a quality judge for an AI engineering swarm.
Score 0-100. Set passed=true only if score >= 75 and no blocking required_fixes.
Be strict: spec coverage, constitution compliance, and substantive output matter.
Return structured JSON only."""


def evaluate(
    role: str,
    rubric: str,
    ctx: TaskContext,
    result: WorkerResult,
) -> JudgeVerdict:
    agent = make_agent(f"{role}_judge", JUDGE_SYSTEM, "judge")
    prompt = f"""Role under review: {role}
Rubric:
{rubric}

Spec excerpt (first 4000 chars):
{ctx.spec[:4000]}

Worker output:
{result.output[:8000]}

Files touched: {list(result.files.keys()) if result.files else 'none'}
Attempts so far: {result.attempts}
"""
    try:
        response = agent(prompt, structured_output_model=JudgeVerdict)
    except Exception as exc:
        return JudgeVerdict(
            passed=False,
            score=0,
            reasons=[f"Judge Bedrock call failed: {exc}"],
            required_fixes=["Retry the stage after checking runtime logs and model access."],
        )
    parsed = response.structured_output
    if parsed is not None:
        return parsed
    return JudgeVerdict(
        passed=False,
        score=0,
        reasons=["Judge returned no structured verdict (guardrail or parse failure)."],
        required_fixes=["Retry the stage; check CloudWatch for guardrail or model errors."],
    )
