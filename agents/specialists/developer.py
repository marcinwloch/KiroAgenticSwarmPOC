from __future__ import annotations

from agents.models import make_agent
from agents.schemas import DeveloperOutput, TaskContext, WorkerResult

SYSTEM = """You are the Developer agent. Implement the spec against the provided repo snapshot.
Return ONLY structured output: changed/new files as path -> full file content.
Follow SOLID, DDD-light layering, pydantic-settings for config, and the constitution.
Scope strictly to the spec â€” no drive-by refactors."""


def _implementation_plan_section(plan: str) -> str:
    """Keep implementation steps; drop threat-model prose that trips PROMPT_ATTACK filters."""
    marker = "## 4. Implementation Steps"
    if marker in plan:
        section = plan[plan.index(marker) :]
        for end in ("\n## 5.", "\n## 6.", "\n## 7.", "\n## 8.", "\n## 9."):
            if end in section:
                section = section[: section.index(end)]
                break
        return section.strip()
    step = "### Step 1:"
    if step in plan:
        return plan[plan.index(step) :].strip()
    return plan[:8_000]


def _guardrail_blocked(result) -> bool:
    if getattr(result, "stop_reason", None) == "guardrail_intervened":
        return True
    text = str(result).lower()
    return "redacted" in text or "guardrail" in text


def run(ctx: TaskContext) -> WorkerResult:
    agent = make_agent("developer", SYSTEM, "developer")
    architect_plan = _implementation_plan_section(ctx.prior.get("architect_output", ""))
    feedback_block = ""
    if ctx.feedback:
        feedback_block = "\n\nJudge feedback:\n" + "\n".join(f"- {f}" for f in ctx.feedback)

    prompt = f"""Spec: {ctx.spec_path}
Repo path: {ctx.repo_path or 'n/a'}

# Specification
{ctx.spec}

# Constitution
{ctx.steering_text()}

# Architect plan
{architect_plan}

# Existing repo files
{ctx.repo_contents_block()}
{feedback_block}

Implement the spec. Include every file you create or modify with complete contents.
"""
    try:
        result = agent(prompt, structured_output_model=DeveloperOutput)
    except Exception as exc:
        return WorkerResult(
            agent="developer",
            output=f"BEDROCK_ERROR: {exc}",
        )
    parsed = result.structured_output
    if parsed is None:
        output = str(result).strip()
        if _guardrail_blocked(result):
            output = (
                "GUARDRAIL_BLOCKED: Bedrock guardrail intervened on developer input/output. "
                "Do not implement locally â€” retry swarm.develop after runtime redeploy."
            )
        return WorkerResult(agent="developer", output=output)
    return WorkerResult(
        agent="developer",
        output=parsed.summary,
        files=dict(parsed.files),
    )
