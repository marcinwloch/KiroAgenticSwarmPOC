from __future__ import annotations

from agents.models import make_agent
from agents.schemas import TaskContext, WorkerResult, TesterOutput

SYSTEM = """You are the Tester agent. Write pytest tests mapping to each acceptance criterion in the spec.
Use httpx AsyncClient + ASGITransport patterns for FastAPI integration tests.
Return structured output with test files (path -> full content). No tautological tests."""


def run(ctx: TaskContext) -> WorkerResult:
    agent = make_agent("tester", SYSTEM, "tester")
    dev_files = ctx.prior.get("developer_files", {})
    dev_summary = ctx.prior.get("developer_output", "")
    feedback_block = ""
    if ctx.feedback:
        feedback_block = "\n\nJudge feedback:\n" + "\n".join(f"- {f}" for f in ctx.feedback)

    dev_block = "\n\n".join(f"### {p}\n```\n{c}\n```" for p, c in sorted(dev_files.items())[:12])

    prompt = f"""Spec: {ctx.spec_path}

# Specification (acceptance criteria)
{ctx.spec}

# Developer summary
{dev_summary}

# Developer files (subset)
{dev_block}

# Baseline repo
{ctx.repo_contents_block(max_chars=20_000)}
{feedback_block}

Add or update tests only. Map each AC to at least one test function name in your summary.
"""
    try:
        result = agent(prompt, structured_output_model=TesterOutput)
    except Exception as exc:
        return WorkerResult(
            agent="tester",
            output=f"BEDROCK_ERROR: {exc}",
        )
    parsed = result.structured_output
    if parsed is None:
        output = str(result).strip()
        if getattr(result, "stop_reason", None) == "guardrail_intervened":
            output = "GUARDRAIL_BLOCKED: Bedrock guardrail intervened on tester stage."
        return WorkerResult(agent="tester", output=output)
    return WorkerResult(agent="tester", output=parsed.summary, files=dict(parsed.files))
