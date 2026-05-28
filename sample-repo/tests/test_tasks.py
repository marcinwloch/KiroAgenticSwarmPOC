import pytest
from httpx import AsyncClient

HEADERS = {"X-API-Key": "test-key"}


@pytest.mark.asyncio
async def test_health_no_auth(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_unauthorized_without_key(client: AsyncClient) -> None:
    response = await client.get("/tasks")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_crud_flow(client: AsyncClient) -> None:
    create = await client.post(
        "/tasks",
        json={"title": "Write tests", "description": "pytest coverage"},
        headers=HEADERS,
    )
    assert create.status_code == 201
    task_id = create.json()["id"]

    listing = await client.get("/tasks", headers=HEADERS)
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    get_one = await client.get(f"/tasks/{task_id}", headers=HEADERS)
    assert get_one.status_code == 200
    assert get_one.json()["title"] == "Write tests"

    updated = await client.put(
        f"/tasks/{task_id}",
        json={"status": "done"},
        headers=HEADERS,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "done"

    deleted = await client.delete(f"/tasks/{task_id}", headers=HEADERS)
    assert deleted.status_code == 204

    missing = await client.get(f"/tasks/{task_id}", headers=HEADERS)
    assert missing.status_code == 404
    assert missing.json()["code"] == "TASK_NOT_FOUND"
