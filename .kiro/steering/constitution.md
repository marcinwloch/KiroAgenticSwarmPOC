---
inclusion: always
---

# Nortal Swarm Constitution

> Definition of done for all specs in this repo. Agents and reviewers MUST comply unless a spec explicitly overrides a rule.

## 1. Architecture

- **SOLID**: single responsibility per module; depend on abstractions (protocols/interfaces), not concrete infra.
- **DDD (lightweight)**: domain logic in `app/domain/` or `app/services/` — never in route handlers beyond orchestration.
- **Layering** (FastAPI PoC): `routers` → `services` → `repositories`/`db`. No SQLAlchemy models imported directly in routers.
- **Configuration**: 12-factor — secrets and tunables from environment variables (`pydantic-settings`), never hardcoded.
- **Dependencies**: prefer stdlib + existing stack; new packages need justification in spec or ADR.

## 2. Code quality

- **Python**: 3.12+, type hints on public functions and service methods.
- **Formatting**: `ruff format` (line length 100).
- **Linting**: `ruff check` — zero warnings on changed files.
- **Naming**: `snake_case` (modules, functions, vars), `PascalCase` (classes), `UPPER_SNAKE` (constants).
- **Errors**: use domain-specific exceptions; map to HTTP status in a single exception handler layer.
- **Logging**: structured JSON via `structlog` in production paths; no `print()`.
- **No dead code**: remove unused imports, commented blocks, and unreachable branches.

## 3. Testing (test pyramid)

| Layer | Target | Tools |
|-------|--------|-------|
| Unit | Domain/services, pure functions | `pytest`, mocks for I/O |
| Integration | API + DB (in-memory SQLite ok) | `pytest`, `httpx.AsyncClient` |
| E2E | Only if spec requires | keep minimal for PoC |

- **Coverage**: every acceptance criterion from the spec has at least one test.
- **AAA pattern**: Arrange → Act → Assert; one logical assertion focus per test.
- **No tautologies**: tests must fail if implementation is removed or broken (Reviewer Judge checks this).
- **Fixtures**: shared setup in `conftest.py`; no copy-paste test boilerplate.

## 4. Security & AWS

- **No secrets in code or logs** (API keys, JWTs, passwords). Use env vars + Bedrock Guardrails patterns.
- **Auth**: validate credentials at dependency/middleware boundary; propagate identity (`sub`, roles) explicitly.
- **Input validation**: Pydantic models for request/response bodies; reject unknown fields where appropriate.
- **Rate limits / PII**: follow spec; return standard headers (`Retry-After`, etc.) when specified.

## 5. API design (REST)

- Resource-oriented URLs, plural nouns (`/tasks`, not `/getTasks`).
- Correct HTTP verbs and status codes (`201` + `Location` on create, `404` not `500` for missing entities).
- Consistent error envelope: `{ "detail": "...", "code": "..." }`.
- OpenAPI must stay accurate after changes.

## 6. Git & delivery

- **Scope**: implement only what the spec describes — no drive-by refactors.
- **Commits mindset**: changes grouped logically; each spec = one focused PR worth of diff.
- **Documentation**: non-obvious decisions → short ADR in `docs/adr/` (Architect agent may add).

## 7. Agent workflow (swarm)

When implementing a spec:

1. Read spec + this constitution before writing code.
2. Architect: design the solution (patterns, technology choices).
3. Developer: implement (minimal diff, compile + lint + run tests).
4. Tester: write/validate tests (map to acceptance criteria).
5. Reviewer: check for issues (min. 3 actionable items tied to spec/constitution).

### MCP-only execution (Kiro)

- **All implementation goes through MCP swarm tools** (`swarm.start` → `swarm.architect` → `swarm.develop` → `swarm.test` → `swarm.review`).
- If a stage returns `status: "error"`, `guardrail_blocked: true`, or score 0 with no files: **stop and report**. Do **not** edit the repo locally as a fallback.
- Retry the same stage after fixes, or ask for help — never bypass the swarm.

## 8. Demo context (sample-repo/)

The swarm target is `sample-repo/` — a FastAPI task tracker with:

- REST API `/tasks` CRUD endpoints
- SQLAlchemy + SQLite database
- Pydantic request/response models
- Example spec: rate-limiting per-IP with slowapi
- Already-completed demo state: rate limiter + 9 tests (all passing)

Use this repo as a launchpad for new specs. Constitution applies to all specs, unless overridden.

## 9. Out of scope (unless spec says otherwise)

- Multi-tenant isolation, IAM Identity Center, production hardening beyond PoC.
- New language profiles beyond `python-fastapi`.
- Cosmetic renames unrelated to the task.
