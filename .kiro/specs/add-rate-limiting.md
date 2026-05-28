# Spec: Add per-IP rate limiting

| Field | Value |
|-------|-------|
| **ID** | `add-rate-limiting` |
| **Status** | Ready |
| **Target codebase** | `sample-repo/` (FastAPI task tracker REST API) |
| **Language profile** | `python-fastapi` |
| **Priority** | P0 — first PoC demo task |

## Summary

Add **per-client-IP rate limiting** to the existing FastAPI task tracker API using **slowapi**. Limits must be configurable via environment variables. When exceeded, return **HTTP 429** with a **`Retry-After`** header. Include pytest integration tests that prove burst rejection and recovery after cooldown. Emit lightweight metrics suitable for **CloudWatch** dashboards.

## Baseline (assumed existing app)

The swarm target is `sample-repo/` with:

- FastAPI app entrypoint (`app/main.py`)
- CRUD routes under `/tasks` (list, create, get, update, delete)
- Simple auth via header `X-API-Key` (unchanged by this spec)
- SQLAlchemy + SQLite, pytest + `httpx.AsyncClient` in `tests/`
- `pyproject.toml` with `ruff`, `pytest`, `httpx`

If baseline files are missing, implement the minimal CRUD skeleton first, then apply this spec — do not skip rate limiting.

## Requirements

### R1 — Rate limiter middleware

- Use **`slowapi`** (`Limiter`, `RateLimitExceeded`, `_rate_limit_exceeded_handler`).
- Key function: **client IP** (`get_remote_address` or equivalent).
- Apply a **default global limit** to all routes unless spec says otherwise.
- Stricter limit on **write** endpoints (`POST`, `PUT`, `PATCH`, `DELETE`) than on **read** (`GET`).

Suggested defaults (override via env):

| Variable | Default | Meaning |
|----------|---------|---------|
| `RATE_LIMIT_READ` | `30/minute` | GET endpoints |
| `RATE_LIMIT_WRITE` | `10/minute` | mutating endpoints |
| `RATE_LIMIT_ENABLED` | `true` | feature toggle |

- Limits parsed from env at startup via **`pydantic-settings`** (constitution §1).
- When `RATE_LIMIT_ENABLED=false`, limiter is bypassed (for local dev/tests).

### R2 — HTTP 429 response

On limit exceeded:

- Status: **429 Too Many Requests**
- Header: **`Retry-After`** — integer seconds until client may retry (must be present and > 0)
- Body: consistent error envelope per constitution:

```json
{
  "detail": "Rate limit exceeded",
  "code": "RATE_LIMIT_EXCEEDED"
}
```

### R3 — Health / docs exclusion

- **`GET /health`** (create if missing) and **`GET /docs`**, **`GET /openapi.json`** must **not** count toward rate limits (or have a separate high ceiling documented in code).

### R4 — Observability

- On each 429, log a structured event (JSON via `structlog` or stdlib `logging` with extra fields):
  - `event=rate_limit_exceeded`
  - `client_ip`
  - `route`
  - `limit`
- Increment a counter metric hook (PoC: log field `metric=RateLimitExceeded` with value `1`; no custom CloudWatch agent required in PoC — logs must be filterable in CloudWatch Logs Insights).

### R5 — Dependencies

- Add `slowapi` to `pyproject.toml` with pinned minimum version.
- Do not add Redis or external store — use in-memory backend (PoC scope).

## Acceptance criteria (Gherkin-light)

### AC1 — Under limit, requests succeed

```gherkin
Given RATE_LIMIT_WRITE=5/minute
And a valid X-API-Key
When the client sends 5 POST /tasks requests within 10 seconds
Then each response status is 201 or 200 (per existing API)
And no response is 429
```

### AC2 — Burst over limit returns 429

```gherkin
Given RATE_LIMIT_WRITE=3/minute
And a valid X-API-Key
When the client sends 4 POST /tasks requests within 5 seconds
Then the 4th response status is 429
And the response includes header Retry-After
And the JSON body has code RATE_LIMIT_EXCEEDED
```

### AC3 — Read limit independent of write limit

```gherkin
Given RATE_LIMIT_READ=20/minute and RATE_LIMIT_WRITE=2/minute
When the client exhausts the write limit with POST /tasks
Then subsequent GET /tasks requests still return 200 until read limit is hit
```

### AC4 — Cooldown recovery

```gherkin
Given RATE_LIMIT_WRITE=2/minute
When the client receives 429 on the 3rd POST within the window
And waits until Retry-After seconds elapse
Then the next POST /tasks succeeds (not 429)
```

### AC5 — Disabled via env

```gherkin
Given RATE_LIMIT_ENABLED=false
When the client sends 50 POST /tasks in 5 seconds
Then no response is 429
```

### AC6 — Health bypass

```gherkin
Given RATE_LIMIT_WRITE=1/minute
When the client sends 100 GET /health requests in 10 seconds
Then all responses are 200
```

## Non-goals

- Per-user or per-API-key quotas (IP only in this spec)
- Redis / distributed rate limiting
- WAF or API Gateway throttling
- Changing authentication mechanism

## Implementation hints (non-binding)

- Register limiter on `app.state.limiter` and exception handler for `RateLimitExceeded`.
- Use `@limiter.limit(...)` decorators or `limiter.limit` on routes; keep limits DRY via settings module.
- Tests: use `httpx.AsyncClient` with `ASGITransport`; patch or set env vars in fixtures; use `time.sleep` or freezegun only if needed for AC4 (prefer parsing `Retry-After` with small limit like `2/second` in tests to keep suite fast).

## Definition of done

- [ ] All acceptance criteria covered by automated tests in `tests/`
- [ ] `ruff check` and `ruff format` pass on changed files
- [ ] `pytest` passes
- [ ] OpenAPI reflects 429 responses where applicable
- [ ] No secrets or hardcoded limits in source
- [ ] Changes scoped to this spec — no unrelated refactors

## Traceability (for Tester agent)

| AC | Suggested test module |
|----|------------------------|
| AC1 | `tests/test_rate_limit.py::test_under_limit_writes_succeed` |
| AC2 | `tests/test_rate_limit.py::test_burst_returns_429_with_retry_after` |
| AC3 | `tests/test_rate_limit.py::test_read_limit_independent_of_write` |
| AC4 | `tests/test_rate_limit.py::test_cooldown_allows_retry` |
| AC5 | `tests/test_rate_limit.py::test_disabled_skips_limiting` |
| AC6 | `tests/test_rate_limit.py::test_health_not_rate_limited` |
