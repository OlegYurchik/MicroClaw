from unittest.mock import AsyncMock, MagicMock
import uuid

import httpx
import pytest

from microclaw.cron.base import BaseCronTask
from microclaw.cron.service import CronService
from microclaw.dto import CronTask


class TestCronService:
    @pytest.mark.asyncio
    async def test_schedule_success(self):
        prev_scheduler = BaseCronTask._scheduler
        prev_tasks = dict(BaseCronTask._tasks)
        try:
            mock_task = MagicMock()
            mock_task.start = AsyncMock()
            mock_factory = AsyncMock(return_value=mock_task)
            service = CronService(task_factory=mock_factory)

            cron_task = CronTask(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                path="test.path",
                cron="0 0 * * *",
                enabled=True,
                args={},
            )
            resolver = MagicMock()
            await service.schedule(cron_task.user_id, cron_task, resolver)
            mock_factory.assert_awaited_once()
            mock_task.start.assert_awaited_once()
        finally:
            BaseCronTask._scheduler = prev_scheduler
            BaseCronTask._tasks.clear()
            BaseCronTask._tasks.update(prev_tasks)

    @pytest.mark.asyncio
    async def test_unschedule_success(self):
        prev_scheduler = BaseCronTask._scheduler
        prev_tasks = dict(BaseCronTask._tasks)
        try:
            scheduler = MagicMock()
            scheduler.running = True
            scheduler.get_job.return_value = MagicMock()
            BaseCronTask._scheduler = scheduler
            BaseCronTask._tasks.clear()

            cron_id = uuid.uuid4()
            key = f"rest_{uuid.uuid4()}_{cron_id}"
            BaseCronTask._tasks[key] = MagicMock()

            service = CronService()
            await service.unschedule(cron_id)

            scheduler.remove_job.assert_called_once_with(key)
            assert key not in BaseCronTask._tasks
        finally:
            BaseCronTask._scheduler = prev_scheduler
            BaseCronTask._tasks.clear()
            BaseCronTask._tasks.update(prev_tasks)

    @pytest.mark.asyncio
    async def test_unschedule_no_tasks(self):
        prev_scheduler = BaseCronTask._scheduler
        try:
            BaseCronTask._scheduler = None
            service = CronService()
            await service.unschedule(uuid.uuid4())
        finally:
            BaseCronTask._scheduler = prev_scheduler


@pytest.mark.asyncio
async def test_list_crons_empty(client: httpx.AsyncClient, regular_user):
    _, token = regular_user
    response = await client.get(
        "/crons",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_list_crons_admin_sees_all(
    client: httpx.AsyncClient, admin_user, regular_user
):
    _, admin_token = admin_user
    user, user_token = regular_user

    await client.post(
        "/crons",
        json={
            "path": "test.path",
            "cron": "0 0 * * *",
            "enabled": True,
            "args": {},
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )

    response = await client.get(
        "/crons",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_list_crons_regular_sees_only_own(
    client: httpx.AsyncClient, regular_user
):
    user, token = regular_user

    await client.post(
        "/crons",
        json={
            "path": "test.path",
            "cron": "0 0 * * *",
            "enabled": True,
            "args": {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/crons",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_list_crons_regular_forbidden_other_user(
    client: httpx.AsyncClient, regular_user, admin_user
):
    admin, _ = admin_user
    _, token = regular_user
    response = await client.get(
        f"/crons?user_id={admin.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_cron(client: httpx.AsyncClient, regular_user):
    _, token = regular_user

    response = await client.post(
        "/crons",
        json={
            "path": "test.path",
            "cron": "0 0 * * *",
            "enabled": True,
            "args": {"key": "val"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["path"] == "test.path"
    assert data["cron"] == "0 0 * * *"
    assert data["enabled"] is True
    assert data["args"] == {"key": "val"}
    assert "id" in data


@pytest.mark.asyncio
async def test_create_cron_invalid_expression(client: httpx.AsyncClient, regular_user):
    _, token = regular_user
    response = await client.post(
        "/crons", json={"path": "test.path", "cron": "invalid", "enabled": True, "args": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_cron_admin_other_user(
    client: httpx.AsyncClient, admin_user, regular_user
):
    user, user_token = regular_user
    _, admin_token = admin_user

    response = await client.post(
        "/crons",
        json={
            "path": "test.path",
            "cron": "0 0 * * *",
            "enabled": True,
            "args": {},
            "user_id": str(user.id),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201

    # Verify the cron belongs to the regular user
    response = await client.get(
        f"/crons?user_id={user.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_create_cron_regular_forbidden_other_user(
    client: httpx.AsyncClient, regular_user, admin_user
):
    admin, _ = admin_user
    _, token = regular_user

    response = await client.post(
        "/crons",
        json={
            "path": "test.path",
            "cron": "0 0 * * *",
            "enabled": True,
            "args": {},
            "user_id": str(admin.id),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_cron(client: httpx.AsyncClient, regular_user):
    _, token = regular_user

    create_resp = await client.post(
        "/crons",
        json={
            "path": "test.path",
            "cron": "0 0 * * *",
            "enabled": True,
            "args": {},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    cron_id = create_resp.json()["id"]

    response = await client.delete(
        f"/crons/{cron_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_cron_not_found(client: httpx.AsyncClient, regular_user):
    _, token = regular_user
    response = await client.delete(
        f"/crons/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_cron_admin_other_user(
    client: httpx.AsyncClient, admin_user, regular_user
):
    _, admin_token = admin_user
    _, user_token = regular_user

    create_resp = await client.post(
        "/crons",
        json={
            "path": "test.path",
            "cron": "0 0 * * *",
            "enabled": True,
            "args": {},
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    cron_id = create_resp.json()["id"]

    response = await client.delete(
        f"/crons/{cron_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204
