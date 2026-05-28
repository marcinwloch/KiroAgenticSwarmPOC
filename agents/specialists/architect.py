from __future__ import annotations

from agents.models import make_agent
from agents.schemas import TaskContext, WorkerResult

SYSTEM = """You are the Architect agent in a spec-driven engineering swarm.
Produce a concise implementation plan aligned with AWS Well-Architected and the steering constitution.
Cover: module layout, key design decisions, env/config, security boundaries, and risks.
Do not write full code â€” leave implementation to the Developer agent.
Output markdown with numbered steps."""


def run(ctx: TaskContext) -> WorkerResult:
    agent = make_agent("architect", SYSTEM, "architect")
    feedback_block = ""
    if ctx.feedback:
        feedback_block = "\n\nJudge feedback to address:\n" + "\n".join(f"- {f}" for f in ctx.feedback)

    prompt = f"""Spec path: {ctx.spec_path}
Action: {ctx.action}

# Specification
{ctx.spec}

# Steering / constitution
{ctx.steering_text()}

# Repository listing
{ctx.repo_listing()}
{feedback_block}
"""
    result = agent(prompt)
    return WorkerResult(agent="architect", output=str(result).strip())
