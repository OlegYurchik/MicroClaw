
import httpx
import pytest

from microclaw.sessions_storages.dto import SessionCreate
from microclaw.users_storages.filters import TokenFilter
from microclaw.users_storages.utils import attach_session_to_user, create_token_for_user


@pytest.mark.asyncio
async def test_list_users_admin(client: httpx.AsyncClient, admin_user):
    _, token = admin_user
    response = await client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["data"], list)
    assert data["total"] is not None


@pytest.mark.asyncio
async def test_list_users_forbidden_for_regular(client: httpx.AsyncClient, regular_user):
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
async def test_create_user_forbidden_for_regular(client: httpx.AsyncClient, regular_user):
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
async def test_get_user_other_forbidden(client: httpx.AsyncClient, admin_user, regular_user):
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
async def test_update_user_other_forbidden(client: httpx.AsyncClient, admin_user, regular_user):
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
async def test_delete_user_forbidden_for_regular(client: httpx.AsyncClient, regular_user):
    user, token = regular_user
    response = await client.delete(
        f"/users/{user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_user_sessions(client: httpx.AsyncClient, regular_user, sessions_storage, users_storage):
    user, token = regular_user
    session_id = (await sessions_storage.create_session(
        data=SessionCreate(channel_key="rest", channel_internal_id=str(user.id))
    )).id
    await attach_session_to_user(
        users_storage, user.id, session_id, "rest", str(user.id)
    )
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
async def test_delete_user_token(client: httpx.AsyncClient, regular_user, users_storage):
    user, token = regular_user
    token_info = await create_token_for_user(users_storage, user_id=user.id)
    response = await client.delete(
        f"/users/{user.id}/tokens/{token_info.token}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204
    assert await users_storage.get_token(filter_=TokenFilter(token={token_info.token})) is None


@pytest.mark.asyncio
async def test_delete_user_token_not_found(client: httpx.AsyncClient, regular_user):
    user, user_token = regular_user
    response = await client.delete(
        f"/users/{user.id}/tokens/nonexistent",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 404
