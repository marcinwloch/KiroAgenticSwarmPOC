---
inclusion: always
---

# Project structure

```
AgenticSwarmPOC/
├── .kiro/
│   ├── settings/mcp.json      # MCP servers for Kiro IDE
│   ├── steering/              # This folder — dev standards & context
│   └── specs/                 # Feature specs with acceptance criteria
│
├── agents/                    # Strands agents (Supervisor + 4 specialists + 4 judges)
│   ├── supervisor.py
│   ├── specialists/           # architect, developer, tester, reviewer
│   ├── judges/                # architect_judge, developer_judge, tester_judge, reviewer_judge
│   ├── runtime/               # FastAPI /invocations for AgentCore Runtime
│   ├── pyproject.toml         # uv-managed Python package (agents bundle)
│   ├── uv.lock
│   ├── Dockerfile             # Builds linux/arm64 image for AgentCore
│   └── requirements.txt
│
├── mcp-server/                # Local MCP bridge (Python, stdio to Kiro)
│   ├── src/swarm_mcp/
│   │   ├── server.py          # Bootstrap, MCP server setup
│   │   ├── tools.py           # Tool definitions (8 swarm tools)
│   │   ├── handlers.py        # Tool dispatch, per-tool handlers
│   │   ├── agentcore_client.py # boto3 wrapper for AgentCore invocation
│   │   ├── context.py         # Spec + repo snapshot builder
│   │   └── sessions.py        # DynamoDB session management
│   ├── tests/                 # pytest suite
│   ├── pyproject.toml         # uv-managed Python package
│   ├── uv.lock
│   └── __init__.py
│
├── sample-repo/               # FastAPI task tracker (demo app / swarm target)
│   ├── app/
│   │   ├── main.py            # FastAPI app with rate-limit middleware
│   │   ├── config.py          # Pydantic settings (12-factor config)
│   │   ├── db.py              # SQLAlchemy + SQLite setup
│   │   ├── limiter.py         # slowapi rate limiter instance
│   │   ├── routers/           # /tasks CRUD endpoints
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic request/response models
│   │   └── services/          # Business logic (domain layer)
│   ├── tests/                 # pytest (9 tests, all passing)
│   ├── Dockerfile
│   └── pyproject.toml         # hatchling-based (demo app)
│
├── scripts/
│   ├── bootstrap.ps1          # One-shot setup (Windows PowerShell)
│   └── bootstrap.sh           # One-shot setup (macOS/Linux Bash)
│
├── docs/
│   └── presentation-en.md     # Full architecture + capacity planning docs
│
├── aws-endpoints.env          # Non-secret AWS endpoints (reference)
├── .gitignore
├── README.md                  # Setup guide + demo instructions
└── [NO infra/cdk/]            # Infrastructure kept in parent repo only
```

## Conventions

- **Specs**: One file per feature in `.kiro/specs/<feature>.md` with Gherkin-light acceptance criteria.
- **Steering**: Dev standards here (constitution, product context, structure, tech stack). Override only in spec when intentional.
- **Dependencies**: Each Python package has `pyproject.toml` + `uv.lock` (uv-managed, no venv in repo).
- **Imports**: Relative to repo root; agents code imports from `agents.X`, MCP from `swarm_mcp.Y`.

## Agent module layout

```
agents/
├── supervisor.py              # Orchestrator: 4 specialists + judges
├── specialists/
│   ├── architect.py           # Design agent (Well-Architected review)
│   ├── developer.py           # Implementation agent (code generation)
│   ├── tester.py              # Test agent (pytest generation)
│   └── reviewer.py            # Review agent (code review)
├── judges/
│   ├── base_judge.py          # Judge base (Nova Lite + structured output)
│   ├── architect_judge.py     # Evaluates architecture
│   ├── developer_judge.py     # Evaluates code
│   ├── tester_judge.py        # Evaluates tests (mutation proxy)
│   └── reviewer_judge.py      # Evaluates review findings
├── schemas.py                 # Pydantic: TaskContext, SwarmReport, JudgeVerdict
├── sessions.py                # DynamoDB session store (short-term storage)
├── models.py                  # Agent model factory (Claude, Nova model IDs)
└── worker_loop.py             # Retry loop: generate → judge → feedback
```

## Naming conventions

- **AWS resources**: Prefix `nortal-swarm-*` or stack name `SwarmStack`
- **DynamoDB**: Table `swarm-sessions` (key: sessionId, GSI: status, timestamp)
- **S3 bucket**: `swarm-artifacts-<account>-eu-central-1` (versioned, KMS-encrypted)
- **Python modules**: `snake_case` (files, functions, vars); `PascalCase` (classes)
- **Constants**: `UPPER_SNAKE` (e.g., `RATE_LIMIT_READ`, `MAX_RETRIES`)

## Git & delivery

- **Scope**: Implement only what spec describes — no drive-by refactors.
- **Commits**: Logical groups; each spec = one PR-worthy diff.
- **Documentation**: Non-obvious decisions → ADR in `docs/adr/` (optional in PoC).
- **Traceability**: Every acceptance criterion (AC) maps to ≥1 test (see Tester Judge).
