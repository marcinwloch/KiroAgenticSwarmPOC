import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.db import init_db
from app.limiter import limiter
from app.routers import tasks
from app.services import tasks as task_service

logger = logging.getLogger(__name__)
@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Task Tracker", version="0.1.0", lifespan=lifespan)

# Attach limiter to app state so slowapi middleware can find it (R1)
app.state.limiter = limiter

app.include_router(tasks.router)


# ---------------------------------------------------------------------------
# Routes not subject to rate limits (R3)
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict[str, str]:
    """Health check — exempt from rate limiting (R3, AC6)."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Domain exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(task_service.TaskNotFoundError)
async def task_not_found_handler(_request: Request, exc: task_service.TaskNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"detail": f"Task {exc.args[0]} not found", "code": "TASK_NOT_FOUND"},
    )


# ---------------------------------------------------------------------------
# Custom 429 handler — structured log + consistent error envelope (R2, R4)
# ---------------------------------------------------------------------------
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    client_ip = get_remote_address(request)
    route = request.url.path
    limit = str(exc.detail) if exc.detail else "unknown"

    # R4 — structured log event filterable in CloudWatch Logs Insights:
    #   fields @timestamp, client_ip, route | filter event = "rate_limit_exceeded"
    logger.warning(
        "rate_limit_exceeded",
        extra={
            "event": "rate_limit_exceeded",
            "client_ip": client_ip,
            "route": route,
            "limit": limit,
            "metric": "RateLimitExceeded",
            "metric_value": 1,
        },
    )

    # Determine Retry-After from the exception; fall back to 60 s (R2)
    retry_after: int = 60
    if hasattr(exc, "retry_after") and exc.retry_after:
        retry_after = int(exc.retry_after)

    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(retry_after)},
        content={"detail": "Rate limit exceeded", "code": "RATE_LIMIT_EXCEEDED"},
    )
