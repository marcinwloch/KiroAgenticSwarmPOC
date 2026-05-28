from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class JudgeVerdict(BaseModel):
    passed: bool
    score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)


class WorkerResult(BaseModel):
    agent: str
    output: str
    files: dict[str, str] = Field(default_factory=dict)
    attempts: int = 1
    verdict: JudgeVerdict | None = None


class SwarmReport(BaseModel):
    status: Literal["ok", "partial", "error"] = "ok"
    action: str
    session_id: str
    architect: WorkerResult | None = None
    developer: WorkerResult | None = None
    tester: WorkerResult | None = None
    reviewer: WorkerResult | None = None
    judge_scores: dict[str, int] = Field(default_factory=dict)
    proposed_files: dict[str, str] = Field(default_factory=dict)
    cost_usd: float = 0.0
    duration_s: float = 0.0
    trace_id: str | None = None
    notes: list[str] = Field(default_factory=list)


class DeveloperOutput(BaseModel):
    summary: str
    files: dict[str, str] = Field(default_factory=dict)


class TesterOutput(BaseModel):
    summary: str
    files: dict[str, str] = Field(default_factory=dict)


class ReviewerOutput(BaseModel):
    summary: str
    findings: list[str] = Field(default_factory=list)
    approved: bool = False


class TaskContext(BaseModel):
    action: str
    spec_path: str
    spec: str
    steering: dict[str, str] = Field(default_factory=dict)
    repo_path: str | None = None
    repo_files: list[str] = Field(default_factory=list)
    repo_contents: dict[str, str] = Field(default_factory=dict)
    prior: dict[str, Any] = Field(default_factory=dict)
    feedback: list[str] = Field(default_factory=list)

    def steering_text(self) -> str:
        if not self.steering:
            return "(no steering documents)"
        return "\n\n".join(f"## {name}\n{body}" for name, body in sorted(self.steering.items()))

    def repo_listing(self) -> str:
        if not self.repo_files:
            return "(empty or missing repo snapshot)"
        return "\n".join(f"- {path}" for path in self.repo_files)

    def repo_contents_block(self, max_chars: int = 40_000) -> str:
        if not self.repo_contents:
            return "(no file contents in snapshot)"
        chunks: list[str] = []
        total = 0
        for path, content in sorted(self.repo_contents.items()):
            block = f"### {path}\n```\n{content}\n```"
            if total + len(block) > max_chars:
                chunks.append(f"### {path}\n(truncated — snapshot limit reached)")
                break
            chunks.append(block)
            total += len(block)
        return "\n\n".join(chunks)
