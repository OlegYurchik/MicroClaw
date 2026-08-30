import secrets

import httpx
import pytest

from microclaw.users_storages.dto import TokenCreate
from microclaw.users_storages.filters import TokenFilter
from microclaw.utils import utcnow


@pytest.mark.asyncio
async def test_list_users_admin(client: httpx.AsyncClient, admin_user):
    _, token = admin_user
    response = await client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["data"], list)
    assert data["total"] is not None


@pytest.mark.asyncio
async def test_list_users_forbidden_for_regular(
    client: httpx.AsyncClient, regular_user
):
    _, token = regular_user
    response = await client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_user_admin(client: httpx.AsyncClient, admin_user):
    _, token = admin_user
    response = await client.post(
        "/users",
        json={"role": "user"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "user"


@pytest.mark.asyncio
async def test_create_user_forbidden_for_regular(
    client: httpx.AsyncClient, regular_user
):
    _, token = regular_user
    response = await client.post(
        "/users",
        json={"role": "user"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_user_self(client: httpx.AsyncClient, regular_user):
    user, token = regular_user
    response = await client.get(
        f"/users/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)


@pytest.mark.asyncio
async def test_get_user_other_forbidden(
    client: httpx.AsyncClient, admin_user, regular_user
):
    admin, _ = admin_user
    _, user_token = regular_user
    response = await client.get(
        f"/users/{admin.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_user_self(client: httpx.AsyncClient, regular_user):
    user, token = regular_user
    response = await client.patch(
        f"/users/{user.id}",
        json={"agent": {"model": "gpt-4"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["agent"] == {"model": "gpt-4"}


@pytest.mark.asyncio
async def test_update_user_other_forbidden(
    client: httpx.AsyncClient, admin_user, regular_user
):
    admin, _ = admin_user
    _, user_token = regular_user
    response = await client.patch(
        f"/users/{admin.id}",
        json={"agent": {"model": "gpt-4"}},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_user_admin(client: httpx.AsyncClient, admin_user, regular_user):
    _, admin_token = admin_user
    user, _ = regular_user
    response = await client.delete(
        f"/users/{user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_user_forbidden_for_regular(
    client: httpx.AsyncClient, regular_user
):
    user, token = regular_user
    response = await client.delete(
        f"/users/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_user_sessions(
    client: httpx.AsyncClient, regular_user, session_factory
):
    user, token = regular_user
    session_id = await session_factory(user)
    response = await client.get(
        f"/users/{user.id}/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert str(session_id) in response.json()["data"]


@pytest.mark.asyncio
async def test_create_user_token(client: httpx.AsyncClient, regular_user):
    user, token = regular_user
    response = await client.post(
        f"/users/{user.id}/tokens",
        json={"ttl_days": 7},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "token" in response.json()
    assert response.json()["expires_at"] is not None


@pytest.mark.asyncio
async def test_delete_user_token(
    client: httpx.AsyncClient, regular_user, users_storage
):
    import datetime

    user, token = regular_user
    token_obj = await users_storage.create_token(
        data=TokenCreate(
            user_id=user.id,
            token=secrets.token_urlsafe(32),
            expires_at=utcnow() + datetime.timedelta(days=1),
        )
    )
    response = await client.delete(
        f"/users/{user.id}/tokens/{token_obj.token}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204
    tokens = []
    async for t in users_storage.get_tokens(
        filter_=TokenFilter(token={token_obj.token})
    ):
        tokens.append(t)
    assert len(tokens) == 0


@pytest.mark.asyncio
async def test_delete_user_token_not_found(client: httpx.AsyncClient, regular_user):
    user, user_token = regular_user
    response = await client.delete(
        f"/users/{user.id}/tokens/nonexistent",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403
