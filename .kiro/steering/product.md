---
inclusion: always
---

# Product — Nortal Kiro Swarm PoC (Demo)

## Purpose

Spec-driven multi-agent code generation system on **AWS Bedrock AgentCore**:
- Kiro IDE (local) → MCP server (local Python) → AgentCore Runtime (AWS) → 4 specialists + 4 judges
- Demo target: FastAPI task tracker with rate-limiting implementation

## Demo Users

- **Nortal engineering**: Evaluate swarm capabilities on a real spec
- **Potential clients**: Hands-on walkthrough of spec → implementation → tests → review
- **R&D**: Baseline for 600-dev capacity planning (not in this demo, documented in `docs/presentation-en.md`)

## Key Capabilities (This Demo)

1. **Spec-driven**: Write `.kiro/specs/add-rate-limiting.md` → swarm implements it
2. **Staged execution**: `swarm.start` → `swarm.architect` → `swarm.develop` → `swarm.test` → `swarm.review`
   - See live progress in Kiro chat
   - Each stage ~1–4 minutes
   - Judge scores for each stage
3. **Artifacts**: Generated code (diff), test suite (pytest), judge verdicts in CloudWatch / DynamoDB
4. **Observability**: CloudWatch logs + X-Ray traces for each session

## What's Included

- **agents/**: Supervisor + 4 specialists (Architect, Developer, Tester, Reviewer) + 4 judges (Nova Lite, structured output)
- **mcp-server/**: Local MCP bridge that connects Kiro to the swarm runtime
- **sample-repo/**: FastAPI task tracker — the app the swarm improves
  - Already has rate-limiting implementation (post-swarm state)
  - 9 passing pytest tests (all AC1–AC6 criteria covered)
  - Shows output quality of the swarm
- **.kiro/steering/**: Development constitution (SOLID, DDD, test pyramid)
- **.kiro/specs/**: Example spec (add-rate-limiting) with Gherkin-light acceptance criteria

## Non-goals (PoC)

- Multi-tenant / 600 dev rollout (documented separately in `docs/`)
- Production SLA, IAM Identity Center, chargeback
- Deployment tooling or CI/CD pipeline (infra kept in parent repo)
- New language profiles beyond `python-fastapi`

## Success Criteria (PoC)

✅ One spec end-to-end: `.kiro/specs/add-rate-limiting.md` → implemented code → tests → judge scores
✅ All 9 tests passing (FastAPI rate limiter with AC1–AC6 traceability)
✅ Client can clone repo + `uv sync` + open Kiro and run `swarm.start` → see 8 tools
✅ Smoke test passes: `python -m swarm_mcp.server --self-test` → "8 tools registered"

## Narrative

> The swarm takes a spec and produces production-ready code:
> - **Architect**: "Here's the design; should use slowapi + env config"
> - **Developer**: "Here's the code; slowapi middleware + Pydantic config"
> - **Tester**: "Here are pytest tests for AC1–AC6; all green"
> - **Reviewer**: "3 findings: env defaults, health exclusion, Retry-After header. All fixed."
> - Result: Ready-to-merge PR with rate-limiting fully implemented, tested, and reviewed.
