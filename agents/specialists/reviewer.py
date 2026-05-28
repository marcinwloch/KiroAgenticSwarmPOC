from __future__ import annotations

from agents.models import make_agent
from agents.schemas import ReviewerOutput, TaskContext, WorkerResult

SYSTEM = """You are the Reviewer agent. Review architect plan, developer code, and tester coverage
against the spec and constitution. Provide at least 3 actionable findings OR approve with evidence.
Nitpicks alone are insufficient. Be specific (file, rule, AC id)."""


def run(ctx: TaskContext) -> WorkerResult:
    agent = make_agent("reviewer", SYSTEM, "reviewer")
    feedback_block = ""
    if ctx.feedback:
        feedback_block = "\n\nPrior judge feedback:\n" + "\n".join(f"- {f}" for f in ctx.feedback)

    prompt = f"""Spec: {ctx.spec_path}

# Specification
{ctx.spec}

# Constitution
{ctx.steering_text()}

# Architect
{ctx.prior.get('architect_output', '')}

# Developer
{ctx.prior.get('developer_output', '')}

# Tester
{ctx.prior.get('tester_output', '')}
{feedback_block}

Produce structured review: summary, findings list, approved bool.
"""
    result = agent(prompt, structured_output_model=ReviewerOutput)
    parsed = result.structured_output
    if parsed is None:
        return WorkerResult(agent="reviewer", output=str(result).strip())
    findings_text = "\n".join(f"- {f}" for f in parsed.findings)
    output = f"{parsed.summary}\n\nFindings:\n{findings_text}\n\nApproved: {parsed.approved}"
    return WorkerResult(agent="reviewer", output=output)
