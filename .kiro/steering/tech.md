---
inclusion: always
---

# Technology Stack

## Cloud (AWS Bedrock, eu-central-1)

| Layer | Choice |
|-------|--------|
| Region | `eu-central-1` (Frankfurt) |
| Agents runtime | AWS Bedrock AgentCore + Strands Agents SDK (Python) |
| Models | Claude Sonnet 4.5 (architects/developers), Nova Lite (judges) |
| Memory | AgentCore Memory (short-term: session; long-term: lessons learned) |
| Guardrails | Bedrock Guardrails (PII/secrets/prompt-injection blocking) |
| Storage | S3 (artifacts), DynamoDB (sessions), CloudWatch (logs) |
| MCP | Python official SDK (stdio bridge Kiro ↔ AgentCore) |

## Application Target (sample-repo/)

- **Python 3.12+**, FastAPI, SQLAlchemy, SQLite
- **Rate limiting**: slowapi (in-memory, per-IP bucket)
- **Testing**: pytest + httpx AsyncClient (async test client)
- **Linting/formatting**: ruff (line length 100, Python 3.12 target)
- **Config**: pydantic-settings (12-factor, env vars)
- **Logging**: stdlib logging (structured events for CloudWatch)

## Local Dev Environment (Windows/Mac/Linux)

### Required

- **Python 3.12+** (uv will provision if needed)
- **uv 0.11+** (package manager & virtualenv manager)
- **AWS CLI v2** (credential management)
- **Kiro IDE** (dev environment + MCP client)
- **Git 2.40+** (version control)

### Optional

- **Docker Desktop** (only if rebuilding agents runtime image; not needed for demo)
- **Node.js 20+** (only if modifying CDK infra; not included in demo)

## Package Management

Each Python component is independently managed with uv:

- **agents/**: `pyproject.toml` + `uv.lock` (Strands SDK, boto3, FastAPI for runtime)
- **mcp-server/**: `pyproject.toml` + `uv.lock` (mcp SDK, boto3, pydantic)
- **sample-repo/**: `pyproject.toml` (hatchling, not uv; can be upgraded separately)

No `.venv/` folders are committed; clients run `uv sync` to set up.

## Credentials & Secrets

- **AWS access keys**: Configured via `aws configure --profile nortal-swarm`
- **MCP env vars**: Set in `.kiro/settings/mcp.json` (non-secret AgentCore endpoints)
- **No secrets in repo**: Bedrock Guardrails enforces this server-side

## Observability

| Component | Method | Destination |
|-----------|--------|-------------|
| Agent execution | structlog (JSON) | CloudWatch Logs (`/aws/agentcore/swarm`) |
| API responses | stdlib logging | Same log group |
| Traces | X-Ray (optional) | AWS X-Ray service |
| Metrics | CloudWatch Metrics | CloudWatch dashboards |
| Judge verdicts | JSON (DynamoDB item) | `swarm-sessions` table |

---

**Infrastructure (CDK, VPC, etc.) is in the parent repo only — not included in this client demo.**
