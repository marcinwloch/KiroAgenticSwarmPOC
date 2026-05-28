# Marcin Włoch Kiro Swarm PoC — Client Demo

**Multi-agent system for spec-driven code generation using AWS Bedrock AgentCore + Kiro IDE + Model Context Protocol (MCP).**

This repository contains a working demo of the Marcin Włoch Kiro Swarm: a supervisor agent + 4 specialist agents (Architect, Developer, Tester, Reviewer), each with a dedicated LLM-as-Judge, running on AWS Bedrock AgentCore.

**What you get:**
- A FastAPI sample repository (`sample-repo/`) with a working implementation of rate-limiting (already completed by the swarm).
- MCP bridge (`mcp-server/`) that connects your Kiro IDE to our AWS-hosted swarm runtime.
- Full source code of specialists, judges, supervisory logic, and observability wiring.
- End-to-end demo: pull a spec, run the swarm, inspect judge scores, view generated code.

---

## Architecture (PoC single-tenant, eu-central-1)

```
┌─────────────────────────────────────────────────────────────────┐
│ Developer Workstation                                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐        ┌──────────────────────────────┐   │
│  │   Kiro IDE      │───────▶│  MCP server (local Python)   │   │
│  │ .kiro/specs/*.md│        │  swarm_mcp.server (stdio)    │   │
│  │ chat panel      │        └──────────────────────────────┘   │
│  └─────────────────┘               │                            │
│                                    │ AWS SigV4 (InvokeAgentRuntime) │
└────────────────────────────────────┼──────────────────────────────┘
                                     │
                    ┌────────────────┴──────────────────┐
                    │                                   │
                    ▼                                   ▼
            ┌───────────────────┐           ┌──────────────────┐
            │  AgentCore        │           │  DynamoDB        │
            │  Runtime          │           │  swarm-sessions  │
            │  (Supervisor +    │           │  (session state  │
            │   4 Specialists   │           │   + scores)      │
            │   + 4 Judges)     │           └──────────────────┘
            │                   │
            │  ├ Architect      │
            │  ├ Developer      │
            │  ├ Tester        │
            │  ├ Reviewer      │
            │  + Judges        │
            └───────┬───────────┘
                    │
                    ├─▶ Bedrock API (Claude Sonnet, Nova Lite)
                    ├─▶ S3 (artifacts, CloudWatch logs)
                    └─▶ Bedrock Guardrails (PII/secrets)

```

---

## Prerequisites

- **Python 3.12+** (uv will download if needed)
- **Kiro IDE** — download from [kiro.dev](https://kiro.dev)
- **AWS CLI v2** and credentials configured (`aws configure --profile nortal-swarm`)
- **uv** — will be installed by bootstrap script if needed
- **Docker Desktop** (optional; only if you plan to rebuild the runtime)

### AWS Credentials

You will receive a separate message with:
- AWS Access Key ID
- AWS Secret Access Key

Configure them:

```bash
aws configure --profile nortal-swarm
# AWS Access Key ID: [paste your key]
# AWS Secret Access Key: [paste your secret]
# Default region: eu-central-1
# Default output: json
```

Verify:

```bash
aws sts get-caller-identity --profile nortal-swarm
```

---

## Quick Start (5 minutes)

### 1. Clone the repository

```bash
git clone https://github.com/marcinwloch/KiroAgenticSwarmPOC.git
cd KiroAgenticSwarmPOC
```

### 2. Configure AWS credentials

```bash
aws configure --profile nortal-swarm
# Paste the credentials sent separately
```

### 3. Run bootstrap script

**Windows (PowerShell):**

```powershell
.\scripts\bootstrap.ps1
```

**macOS/Linux (Bash):**

```bash
bash scripts/bootstrap.sh
```

This will:
- Install `uv` if needed
- Run `uv sync` in `mcp-server/` (installs MCP + dependencies)
- Patch `.kiro/settings/mcp.json` with **absolute paths** (Kiro does not expand `${workspaceFolder}`)
- Run `--self-test` to verify configuration
- Print next steps

### 4. Open in Kiro IDE

1. **File → Open Folder** → select this repo's root (`KiroAgenticSwarmPOC`, not a parent folder)
2. Kiro loads `.kiro/settings/mcp.json` (patched by bootstrap in step 3)
3. **Reload MCP servers** if Kiro was already open during bootstrap
3. In the MCP panel, you should see **`nortal-swarm`** with **8 tools** listed:
   - `swarm.start`
   - `swarm.architect`, `swarm.develop`, `swarm.test`, `swarm.review`
   - `swarm.status`, `swarm.plan`, `swarm.implement`

### 5. Try the demo

In the Kiro chat, type:

```
Use the nortal-swarm tool to implement the spec at .kiro/specs/add-rate-limiting.md 
against sample-repo. Call swarm.start first, then run stages one by one and report scores.
```

Or manually stage it:

1. `swarm.start { spec_path: ".kiro/specs/add-rate-limiting.md", repo_path: "sample-repo" }` → you get a `session_id`
2. `swarm.architect { session_id }` → Architect designs the solution (~2 min)
3. `swarm.develop { session_id }` → Developer implements (~3 min)
4. `swarm.test { session_id }` → Tester writes/validates tests (~2 min)
5. `swarm.review { session_id }` → Reviewer checks for issues (~1 min)
6. `swarm.status { session_id }` → Anytime, check progress + judge scores

> **Tip:** A second, not-yet-implemented example spec ships at
> `.kiro/specs/weather-data-collection/` (requirements + design). Point
> `swarm.start` at `.kiro/specs/weather-data-collection/requirements.md` to watch
> the swarm implement a fresh feature end-to-end.

---

## Repository Structure

```
nortal-swarm-demo/
├── .kiro/
│   ├── settings/mcp.json             # MCP configuration for Kiro
│   ├── steering/
│   │   ├── constitution.md           # Development standards (SOLID, DDD, testing)
│   │   ├── product.md                # Product context
│   │   ├── structure.md              # Repo layout
│   │   └── tech.md                   # Tech stack notes
│   └── specs/
│       ├── add-rate-limiting.md      # Example spec (already implemented in sample-repo)
│       └── weather-data-collection/  # Example spec (requirements + design, ready to run)
│           ├── requirements.md       # EARS-style acceptance criteria
│           ├── design.md             # Technical design
│           └── .config.kiro          # Kiro spec metadata
│
├── agents/                            # Swarm agents (Strands SDK on AgentCore)
│   ├── supervisor.py                 # Orchestrates 4 specialists + judges
│   ├── core_init.py                  # Shared runtime/bootstrap helpers
│   ├── runtime/
│   │   └── main.py                   # FastAPI runtime server (AgentCore entry)
│   ├── specialists/                  # architect.py, developer.py, tester.py, reviewer.py
│   ├── judges/                       # base_judge.py + one judge per specialist (Nova Lite)
│   ├── schemas.py, sessions.py       # Data models + DynamoDB helpers
│   ├── models.py, worker_loop.py     # Agent model factory + retry loop
│   ├── pyproject.toml                # uv-managed Python package
│   ├── uv.lock                       # Dependency lock file
│   ├── Dockerfile                    # Container for AgentCore runtime
│   └── requirements.txt              # (Legacy; use uv.lock)
│
├── mcp-server/                        # Local MCP bridge to AgentCore
│   ├── src/swarm_mcp/
│   │   ├── server.py                 # Bootstrap + stdio entry + --self-test
│   │   ├── tools.py                  # 8 tool definitions
│   │   ├── handlers.py               # Tool dispatchers + call_tool handlers
│   │   ├── agentcore_client.py       # boto3 wrapper for InvokeAgentRuntime
│   │   ├── context.py                # Spec + repo snapshot builder
│   │   └── sessions.py               # DynamoDB session helpers
│   ├── pyproject.toml                # uv-managed Python package
│   └── uv.lock                       # Dependency lock file
│
├── sample-repo/                       # FastAPI task tracker (swarm target)
│   ├── app/
│   │   ├── main.py                   # FastAPI app + 429 handler + lifespan
│   │   ├── config.py                 # Pydantic settings
│   │   ├── db.py                     # SQLAlchemy + SQLite setup
│   │   ├── limiter.py                # slowapi rate limiter instance
│   │   ├── dependencies/auth.py      # API key auth dependency
│   │   ├── routers/tasks.py          # /tasks CRUD endpoints
│   │   ├── models/task.py            # SQLAlchemy ORM model
│   │   ├── schemas/task.py           # Pydantic request/response
│   │   └── services/tasks.py         # Business logic
│   ├── tests/                        # conftest.py, test_rate_limit.py, test_tasks.py
│   ├── Dockerfile
│   └── pyproject.toml                # hatchling (sample app)
│
├── scripts/
│   ├── bootstrap.ps1                 # Windows setup
│   └── bootstrap.sh                  # macOS/Linux setup
│
├── aws-endpoints.env                 # Non-secret AWS endpoints (reference)
├── .gitignore
└── README.md                         # (this file)
```

---

## How to Inspect Swarm Output

The swarm has already run against the spec `add-rate-limiting.md` for this demo. The result is committed in `sample-repo/`:

### 1. Review the generated code

```bash
cd sample-repo

# View generated files
cat app/main.py              # See 429 handler, rate limit middleware
cat app/limiter.py           # slowapi configuration
cat app/config.py            # RATE_LIMIT_READ, RATE_LIMIT_WRITE env vars

# View tests
cat tests/test_rate_limit.py # Traces to AC1–AC6 acceptance criteria
```

### 2. Run the tests locally

```bash
cd sample-repo

# Install dev dependencies
pip install -e .[dev]

# Run pytest
pytest -v

# Run with coverage (optional)
pytest --cov=app tests/
```

### 3. View acceptance criteria traceability

The spec is at `.kiro/specs/add-rate-limiting.md`. Each acceptance criterion (AC1–AC6) maps to a test in `tests/test_rate_limit.py`:

- **AC1** → `test_under_limit_writes_succeed`
- **AC2** → `test_burst_returns_429_with_retry_after`
- **AC3** → `test_read_limit_independent_of_write`
- **AC4** → `test_cooldown_allows_retry`
- **AC5** → `test_disabled_skips_limiting`
- **AC6** → `test_health_not_rate_limited`

---

## Development Standards (Constitution)

All code follows the constitution in `.kiro/steering/constitution.md`:

- **Architecture**: SOLID principles, DDD layering (routers → services → repositories)
- **Code quality**: Python 3.12+, type hints, ruff formatting (line length 100)
- **Testing**: Test pyramid (unit + integration + E2E); no tautologies; AAA pattern
- **API design**: REST, resource-oriented URLs, consistent error envelopes
- **Security**: No hardcoded secrets; input validation via Pydantic
- **Observability**: Structured JSON logging via `structlog`

---

## Agents & Judges Explained

### Specialists (Workers)

Each specialist runs in the `agents/runtime/main.py` FastAPI server, invoked by the Supervisor:

1. **Architect** (`agents/specialists/architect.py`)
   - Analyzes spec + repo
   - Makes design decisions (patterns, technology choices, ADRs)
   - Output: architecture notes, ADR proposal

2. **Developer** (`agents/specialists/developer.py`)
   - Implements the spec (writes Python/SQL/etc.)
   - Compiles & lints in AgentCore sandbox
   - Output: diff, modified files

3. **Tester** (`agents/specialists/tester.py`)
   - Writes pytest tests
   - Checks mutation testing proxy (anti-tautology)
   - Output: test code + coverage report

4. **Reviewer** (`agents/specialists/reviewer.py`)
   - Reviews diff + tests
   - Checks spec coverage + constitution compliance
   - Output: review comments + score

### Judges (Verifiers)

Each judge is a lightweight **Nova Lite** LLM that evaluates a specialist's output:

- **Structure**: `agents/judges/{specialist}_judge.py`
- **Pattern**: call `evaluate(task_context, worker_output)` → `{passed: bool, score: 0-100, reasons: [...], required_fixes: [...]}`
- **Retry loop**: if judge fails, specialist gets feedback and retries (max 3 attempts)

---

## MCP Tools Reference

### Staged Execution (Recommended for live chat)

#### `swarm.start { spec_path, repo_path }`
- **Time**: ~1s
- **Returns**: `session_id`, seeded spec preview
- **Next**: `swarm.architect`

#### `swarm.architect { session_id }`
- **Time**: ~2–3 min
- **Returns**: architecture notes + judge score
- **Next**: `swarm.develop`

#### `swarm.develop { session_id }`
- **Time**: ~2–4 min
- **Returns**: generated files (diff) + judge score
- **Next**: `swarm.test`

#### `swarm.test { session_id }`
- **Time**: ~1–3 min
- **Returns**: test code + coverage + judge score
- **Next**: `swarm.review`

#### `swarm.review { session_id }`
- **Time**: ~1–2 min
- **Returns**: review comments + judge score, all stages complete
- **Next**: `swarm.status` (read-only)

#### `swarm.status { session_id }`
- **Time**: ~1s
- **Returns**: progress (e.g., "stage 3 of 4 — architect, developer, tester done"), next stage, all judge scores
- **Use**: Check progress anytime without blocking

### Legacy Single-Shot

#### `swarm.implement { spec_path, repo_path }`
- **Time**: ~10 min (blocks)
- **Returns**: all 4 stages' output + combined judge scores
- **Use**: When you don't need live progress updates

#### `swarm.plan { spec_path }`
- **Time**: ~1–2 min
- **Returns**: Architect stage only (planning / design review)
- **Use**: Pre-review a spec before full implementation

#### `swarm.review { spec_path, repo_path }`
- **Time**: ~1–2 min
- **Returns**: Reviewer stage only (static analysis on existing repo)
- **Use**: Quick code review without full swarm

---

## Costs & Runtime

**This demo runs on Marcin Włoch's AWS account** — you are not billed.

- **Full spec (4 stages)**: ~$0.30–0.60, ~5–10 minutes
- **Bottleneck**: LLM inference (Claude Sonnet for architects/devs, Nova Lite for judges)
- **Session quota**: We can handle ~20 concurrent swarms without throttling

---

## Troubleshooting

### "MCP server not connecting in Kiro"

### "`Project directory ${workspaceFolder}/mcp-server does not exist`" or `No module named 'swarm_mcp'`

Kiro **does not expand** `${workspaceFolder}` in `mcp.json` ([Kiro#5060](https://github.com/kirodotdev/Kiro/issues/5060)). The literal string is passed to `uv`, so the MCP server never starts.

**Fix:** Re-run bootstrap (it patches `mcp.json` to use the venv Python with absolute paths):

```powershell
.\scripts\bootstrap.ps1
```

Then in Kiro: reload MCP servers. The `command` in `.kiro/settings/mcp.json` should look like `D:/.../mcp-server/.venv/Scripts/python.exe`, not `uv` with `${workspaceFolder}`.

Also ensure you opened the **repo root** as the workspace folder (the directory that contains `mcp-server/`).

### "`[Powers Debug] No powers.mcpServers section found`"

Harmless Kiro internal warning. Ignore it if `[nortal-swarm] Successfully connected` appears in the log.

### "MCP server not connecting in Kiro" (general)

**Check:**

1. Bootstrap completed step 3 (`Patched .kiro/settings/mcp.json`)
2. MCP config: `.kiro/settings/mcp.json` exists and `command` points to `mcp-server/.venv/.../python`
3. Workspace folder is the repo root (contains `mcp-server/`)
4. Logs: Kiro **View → Output** panel, select MCP channel

**Quick test (command line):**

Prefer `scripts/bootstrap.ps1` or `scripts/bootstrap.sh` - they patch `mcp.json` and load `aws-endpoints.env` before `--self-test`.

Manual run (must set env vars first; Kiro injects these from `.kiro/settings/mcp.json`):

```bash
# macOS/Linux
set -a && source ../aws-endpoints.env && set +a
cd mcp-server
uv run python -m swarm_mcp.server --self-test
```

```powershell
# Windows: use .\scripts\bootstrap.ps1 (loads aws-endpoints.env automatically)
```

Must print: `OK: nortal-swarm-mcp loaded, 8 tools registered` and `config: AgentCore client OK`

### "AccessDeniedException from Bedrock"

**Check:**

1. AWS credentials: `aws sts get-caller-identity --profile nortal-swarm`
2. Profile name: Must be `nortal-swarm` (set in mcp.json `AWS_PROFILE`)
3. Bedrock models enabled in account: (handled by Marcin Włoch, not your side)

### "Session timeout or no response"

Stages can take 5–10 minutes. Default timeout is **300 seconds per stage**. If needed:

```json
{
  "env": {
    "SWARM_STAGE_TIMEOUT_SEC": "600"
  }
}
```

### "Guardrail blocked my input"

Bedrock Guardrails blocks:
- AWS access keys / secret keys
- PII (emails, phone numbers)
- JWT tokens
- Prompt injection patterns

Rephrase the spec or ensure no secrets are in `.kiro/specs/*.md`.

---

## Next Steps & Extension

### Add a new spec

1. Create `.kiro/specs/my-feature.md` (follow format of `add-rate-limiting.md`, or the
   richer multi-file layout in `.kiro/specs/weather-data-collection/`)
2. Add acceptance criteria (EARS / Gherkin-light format)
3. In Kiro chat: `swarm.start { spec_path: ".kiro/specs/my-feature.md", repo_path: "sample-repo" }`
4. Run stages or `swarm.implement` (blocks)

### Understand agent prompts

Each specialist has a system prompt in `agents/specialists/{name}.py`. Prompts reference:
- `.kiro/steering/constitution.md` (injected as "development constitution")
- Language profile metadata (detected from `pyproject.toml` / `package.json` / etc.)

### Extend to other languages

The architecture is language-agnostic. To add e.g. **TypeScript + Node**:

1. Create `agents/language_profiles/typescript-node.yaml` (define detect/build/test/lint/format commands)
2. Architect Agent auto-detects `package.json` + loads the profile
3. Agent prompts are unchanged (they reference the profile, not hardcoded Python)

---

## Support & Questions

- **Technical**: Review docs in `.kiro/steering/` and the example specs in `.kiro/specs/`
- **Contact**: Marcin Włoch [contact email — provided separately]
- **Report issues**: Check the troubleshooting section above or reach out to Marcin Włoch

---

## License

Internal R&D / PoC. Not for distribution.

---

**Happy coding!**
