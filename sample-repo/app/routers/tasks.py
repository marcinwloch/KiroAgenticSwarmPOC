from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.dependencies.auth import require_api_key
from app.limiter import limiter
from app.schemas.task import ErrorResponse, TaskCreate, TaskRead, TaskUpdate
from app.services import tasks as task_service

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(require_api_key)])

# Shared 429 response spec for OpenAPI (R2)
_429 = {429: {"description": "Rate limit exceeded — see Retry-After header"}}


@router.get("", response_model=list[TaskRead], responses=_429)
@limiter.limit(lambda: settings.rate_limit_read)
async def list_tasks(request: Request, session: AsyncSession = Depends(get_session)) -> list[TaskRead]:
    return await task_service.list_tasks(session)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED, responses=_429)
@limiter.limit(lambda: settings.rate_limit_write)
async def create_task(
    request: Request,
    data: TaskCreate,
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    return await task_service.create_task(session, data)


@router.get("/{task_id}", response_model=TaskRead, responses={404: {"model": ErrorResponse}, **_429})
@limiter.limit(lambda: settings.rate_limit_read)
async def get_task(
    request: Request,
    task_id: int,
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    return await task_service.get_task(session, task_id)


@router.put("/{task_id}", response_model=TaskRead, responses={404: {"model": ErrorResponse}, **_429})
@limiter.limit(lambda: settings.rate_limit_write)
async def update_task(
    request: Request,
    task_id: int,
    data: TaskUpdate,
    session: AsyncSession = Depends(get_session),
) -> TaskRead:
    return await task_service.update_task(session, task_id, data)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}, **_429},
)
@limiter.limit(lambda: settings.rate_limit_write)
async def delete_task(
    request: Request,
    task_id: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    await task_service.delete_task(session, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
