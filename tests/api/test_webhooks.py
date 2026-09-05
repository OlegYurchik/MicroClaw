import uuid

import httpx
import pytest


@pytest.mark.asyncio
async def test_list_webhooks_empty(client: httpx.AsyncClient, regular_user):
    _, token = regular_user
    response = await client.get(
        "/webhooks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_list_webhooks_admin_sees_all(client: httpx.AsyncClient, admin_user, regular_user):
    _, admin_token = admin_user
    user, user_token = regular_user

    await client.post(
        "/webhooks",
        json={"path": "test.path", "enabled": True, "args": {}},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    response = await client.get(
        "/webhooks",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_list_webhooks_regular_sees_only_own(client: httpx.AsyncClient, regular_user):
    user, token = regular_user

    await client.post(
        "/webhooks",
        json={"path": "test.path", "enabled": True, "args": {}},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/webhooks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


@pytest.mark.asyncio
async def test_create_webhook(client: httpx.AsyncClient, regular_user):
    _, token = regular_user

    response = await client.post(
        "/webhooks",
        json={"path": "test.path", "enabled": True, "args": {"key": "val"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["path"] == "test.path"
    assert data["enabled"] is True
    assert data["args"] == {"key": "val"}
    assert "id" in data


@pytest.mark.asyncio
async def test_get_webhook(client: httpx.AsyncClient, regular_user):
    _, token = regular_user

    create_resp = await client.post(
        "/webhooks",
        json={"path": "test.path", "enabled": True, "args": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    webhook_id = create_resp.json()["id"]

    response = await client.get(
        f"/webhooks/{webhook_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == webhook_id


@pytest.mark.asyncio
async def test_get_webhook_not_found(client: httpx.AsyncClient, regular_user):
    _, token = regular_user
    response = await client.get(
        f"/webhooks/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_webhook(client: httpx.AsyncClient, regular_user):
    _, token = regular_user

    create_resp = await client.post(
        "/webhooks",
        json={"path": "test.path", "enabled": True, "args": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    webhook_id = create_resp.json()["id"]

    response = await client.delete(
        f"/webhooks/{webhook_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_webhook_not_found(client: httpx.AsyncClient, regular_user):
    _, token = regular_user
    response = await client.delete(
        f"/webhooks/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_call_webhook_not_found(client: httpx.AsyncClient):
    response = await client.post(
        f"/webhooks/{uuid.uuid4()}/call",
        json={"message": "test"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_webhook_with_agent_and_channel(client: httpx.AsyncClient, regular_user):
    _, token = regular_user

    response = await client.post(
        "/webhooks",
        json={
            "path": "microclaw.webhooks.agent_webhook.AgentWebhook",
            "enabled": True,
            "args": {},
            "agent": "default",
            "channel": "telegram",
            "channel_internal_id": "123456",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["path"] == "microclaw.webhooks.agent_webhook.AgentWebhook"
    assert data["agent"] == "default"
    assert data["channel"] == "telegram"
    assert data["channel_internal_id"] == "123456"


@pytest.mark.asyncio
async def test_call_webhook_with_agent_webhook(client: httpx.AsyncClient, regular_user, resolver):
    from unittest.mock import MagicMock

    from tests.conftest import _async_gen

    _, token = regular_user

    # Configure resolver with a mock agent
    agent_mock = MagicMock()
    agent_mock.ask.return_value = _async_gen([])
    resolver.resolve_agents.return_value = {"default": agent_mock}

    create_resp = await client.post(
        "/webhooks",
        json={
            "path": "microclaw.webhooks.agent_webhook.AgentWebhook",
            "enabled": True,
            "args": {},
            "agent": "default",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    webhook_id = create_resp.json()["id"]

    response = await client.post(
        f"/webhooks/{webhook_id}/call",
        json={"text": "Hello from webhook"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    agent_mock.ask.assert_called_once()
    messages = agent_mock.ask.call_args.kwargs["messages"]
    assert len(messages) == 1
    assert "Hello from webhook" in messages[0].text
