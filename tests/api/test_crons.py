from unittest.mock import patch
import uuid

import httpx
import pytest


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
async def test_list_crons_admin_sees_all(client: httpx.AsyncClient, admin_user, regular_user):
    _, admin_token = admin_user
    user, user_token = regular_user

    with patch("microclaw.api.rest.crons.handlers._schedule_cron"):
        await client.post(
            "/crons",
            json={"path": "test.path", "cron": "0 0 * * *", "enabled": True, "args": {}},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    response = await client.get(
        "/crons",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_list_crons_regular_sees_only_own(client: httpx.AsyncClient, regular_user):
    user, token = regular_user

    with patch("microclaw.api.rest.crons.handlers._schedule_cron"):
        await client.post(
            "/crons",
            json={"path": "test.path", "cron": "0 0 * * *", "enabled": True, "args": {}},
            headers={"Authorization": f"Bearer {token}"},
        )

    response = await client.get(
        "/crons",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_create_cron(client: httpx.AsyncClient, regular_user):
    _, token = regular_user

    with patch("microclaw.api.rest.crons.handlers._schedule_cron"):
        response = await client.post(
            "/crons",
            json={"path": "test.path", "cron": "0 0 * * *", "enabled": True, "args": {"key": "val"}},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
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
        "/crons",
        json={"path": "test.path", "cron": "invalid", "enabled": True, "args": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_cron(client: httpx.AsyncClient, regular_user):
    _, token = regular_user

    with patch("microclaw.api.rest.crons.handlers._schedule_cron"):
        create_resp = await client.post(
            "/crons",
            json={"path": "test.path", "cron": "0 0 * * *", "enabled": True, "args": {}},
            headers={"Authorization": f"Bearer {token}"},
        )
    cron_id = create_resp.json()["id"]

    with patch("microclaw.api.rest.crons.handlers._unschedule_cron"):
        response = await client.delete(
            f"/crons/{cron_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_cron_not_found(client: httpx.AsyncClient, regular_user):
    _, token = regular_user
    with patch("microclaw.api.rest.crons.handlers._unschedule_cron"):
        response = await client.delete(
            f"/crons/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 404
