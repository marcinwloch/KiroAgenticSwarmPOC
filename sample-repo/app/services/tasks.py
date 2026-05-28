from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate


class TaskNotFoundError(Exception):
    pass


async def list_tasks(session: AsyncSession) -> list[Task]:
    result = await session.execute(select(Task).order_by(Task.id))
    return list(result.scalars().all())


async def get_task(session: AsyncSession, task_id: int) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise TaskNotFoundError(task_id)
    return task


async def create_task(session: AsyncSession, data: TaskCreate) -> Task:
    task = Task(title=data.title, description=data.description, status=data.status)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def update_task(session: AsyncSession, task_id: int, data: TaskUpdate) -> Task:
    task = await get_task(session, task_id)
    if data.title is not None:
        task.title = data.title
    if data.description is not None:
        task.description = data.description
    if data.status is not None:
        task.status = data.status
    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, task_id: int) -> None:
    task = await get_task(session, task_id)
    await session.delete(task)
    await session.commit()
