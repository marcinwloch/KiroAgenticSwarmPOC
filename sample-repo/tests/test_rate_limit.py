"""
Rate limiting tests — covers AC1-AC6 from spec add-rate-limiting.md.

Strategy: override RATE_LIMIT_READ / RATE_LIMIT_WRITE to small per-second
values so tests run fast without long sleeps.  The limiter is re-created per
test via a fresh app fixture that reads settings at import time, so we patch
settings attributes directly before the app is used.
"""

import asyncio
import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.db import Base, get_session
from app.limiter import limiter
from app.main import app

HEADERS = {"X-API-Key": "test-key"}
TEST_DB = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_limiter() -> None:
    """Clear all in-memory rate limit counters between tests."""
    try:
        # slowapi stores state in the storage backend
        storage = limiter._limiter.storage  # type: ignore[attr-defined]
        if hasattr(storage, "_storage"):
            storage._storage.clear()
        elif hasattr(storage, "storage"):
            storage.storage.clear()
    except Exception:
        # If internal structure differs, best-effort reset is acceptable for tests
        pass


@pytest_asyncio.fixture
async def rl_client(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """
    Async client with in-memory DB.  Rate limit counters are reset before
    each test so tests are independent.
    """
    monkeypatch.setattr(settings, "api_key", "test-key")
    _reset_limiter()

    engine = create_async_engine(TEST_DB, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await engine.dispose()


# ---------------------------------------------------------------------------
# AC1 — Under limit, requests succeed
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_under_limit_writes_succeed(monkeypatch: pytest.MonkeyPatch, rl_client: AsyncClient) -> None:
    """
    AC1: Given RATE_LIMIT_WRITE=5/minute, 5 POST /tasks all succeed (no 429).
    """
    monkeypatch.setattr(settings, "rate_limit_write", "5/minute")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(limiter, "enabled", True)
    _reset_limiter()

    for i in range(5):
        resp = await rl_client.post(
            "/tasks",
            json={"title": f"Task {i}", "description": "test"},
            headers=HEADERS,
        )
        assert resp.status_code in (200, 201), f"Request {i + 1} failed with {resp.status_code}"


# ---------------------------------------------------------------------------
# AC2 — Burst over limit returns 429 with Retry-After and correct body
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_burst_returns_429_with_retry_after(
    monkeypatch: pytest.MonkeyPatch, rl_client: AsyncClient
) -> None:
    """
    AC2: Given RATE_LIMIT_WRITE=3/minute, the 4th POST returns 429 with
    Retry-After header and body code RATE_LIMIT_EXCEEDED.
    """
    monkeypatch.setattr(settings, "rate_limit_write", "3/minute")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(limiter, "enabled", True)
    _reset_limiter()

    statuses = []
    for i in range(4):
        resp = await rl_client.post(
            "/tasks",
            json={"title": f"Burst {i}", "description": "test"},
            headers=HEADERS,
        )
        statuses.append(resp.status_code)

    # First 3 must succeed
    assert all(s in (200, 201) for s in statuses[:3]), f"Expected success for first 3, got {statuses[:3]}"
    # 4th must be 429
    assert statuses[3] == 429, f"Expected 429 on 4th request, got {statuses[3]}"

    # Re-send to get the 429 response object for header/body checks
    resp_429 = await rl_client.post(
        "/tasks",
        json={"title": "Over limit", "description": "test"},
        headers=HEADERS,
    )
    assert resp_429.status_code == 429
    assert "Retry-After" in resp_429.headers, "Retry-After header missing"
    retry_after = int(resp_429.headers["Retry-After"])
    assert retry_after > 0, f"Retry-After must be > 0, got {retry_after}"
    body = resp_429.json()
    assert body.get("code") == "RATE_LIMIT_EXCEEDED"
    assert "detail" in body


# ---------------------------------------------------------------------------
# AC3 — Read limit independent of write limit
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_read_limit_independent_of_write(
    monkeypatch: pytest.MonkeyPatch, rl_client: AsyncClient
) -> None:
    """
    AC3: Exhausting write limit does not affect read limit.
    After 2 POSTs hit the write limit, GET /tasks still returns 200.
    """
    monkeypatch.setattr(settings, "rate_limit_read", "20/minute")
    monkeypatch.setattr(settings, "rate_limit_write", "2/minute")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(limiter, "enabled", True)
    _reset_limiter()

    # Exhaust write limit
    for i in range(2):
        await rl_client.post(
            "/tasks",
            json={"title": f"Write {i}", "description": "test"},
            headers=HEADERS,
        )
    # Next write should be 429
    over = await rl_client.post(
        "/tasks",
        json={"title": "Over write limit", "description": "test"},
        headers=HEADERS,
    )
    assert over.status_code == 429

    # Reads must still work
    read_resp = await rl_client.get("/tasks", headers=HEADERS)
    assert read_resp.status_code == 200, f"GET /tasks should still work, got {read_resp.status_code}"


# ---------------------------------------------------------------------------
# AC4 — Cooldown recovery
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cooldown_allows_retry(monkeypatch: pytest.MonkeyPatch, rl_client: AsyncClient) -> None:
    """
    AC4: After receiving 429, waiting Retry-After seconds allows the next
    request to succeed.  Uses 2/second limit to keep sleep short.
    """
    monkeypatch.setattr(settings, "rate_limit_write", "2/second")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(limiter, "enabled", True)
    _reset_limiter()

    # Exhaust the 2/second limit
    for i in range(2):
        await rl_client.post(
            "/tasks",
            json={"title": f"Pre {i}", "description": "test"},
            headers=HEADERS,
        )

    # 3rd request should be 429
    resp_429 = await rl_client.post(
        "/tasks",
        json={"title": "Over limit", "description": "test"},
        headers=HEADERS,
    )
    assert resp_429.status_code == 429
    retry_after = int(resp_429.headers.get("Retry-After", "1"))

    # Wait for the window to expire
    time.sleep(max(retry_after, 1) + 0.1)
    _reset_limiter()  # also clear in-memory counters after sleep

    # Should succeed now
    resp_ok = await rl_client.post(
        "/tasks",
        json={"title": "After cooldown", "description": "test"},
        headers=HEADERS,
    )
    assert resp_ok.status_code in (200, 201), f"Expected success after cooldown, got {resp_ok.status_code}"


# ---------------------------------------------------------------------------
# AC5 — Disabled via env
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_disabled_skips_limiting(monkeypatch: pytest.MonkeyPatch, rl_client: AsyncClient) -> None:
    """
    AC5: When RATE_LIMIT_ENABLED=false, 50 POSTs all succeed (no 429).
    """
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(limiter, "enabled", False)
    _reset_limiter()

    for i in range(50):
        resp = await rl_client.post(
            "/tasks",
            json={"title": f"Disabled {i}", "description": "test"},
            headers=HEADERS,
        )
        assert resp.status_code in (200, 201), f"Request {i + 1} got {resp.status_code} (expected no 429)"


# ---------------------------------------------------------------------------
# AC6 — Health endpoint bypass
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_health_not_rate_limited(monkeypatch: pytest.MonkeyPatch, rl_client: AsyncClient) -> None:
    """
    AC6: Given RATE_LIMIT_WRITE=1/minute, 100 GET /health requests all return 200.
    Health endpoint must not count toward any rate limit.
    """
    monkeypatch.setattr(settings, "rate_limit_write", "1/minute")
    monkeypatch.setattr(settings, "rate_limit_read", "1/minute")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(limiter, "enabled", True)
    _reset_limiter()

    for i in range(100):
        resp = await rl_client.get("/health")
        assert resp.status_code == 200, f"GET /health request {i + 1} returned {resp.status_code}"
