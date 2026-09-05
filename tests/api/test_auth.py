import httpx
import pytest

from microclaw.users_storages.utils import create_token_for_user


@pytest.mark.asyncio
async def test_me(client: httpx.AsyncClient, regular_user):
    user, token = regular_user
    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)
    assert response.json()["role"] == "user"


@pytest.mark.asyncio
async def test_me_unauthorized(client: httpx.AsyncClient):
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_token_admin_only(client: httpx.AsyncClient, admin_user, regular_user):
    admin, admin_token = admin_user
    user, user_token = regular_user

    response = await client.post(
        "/auth/tokens",
        json={"user_id": str(user.id), "ttl_days": 7},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    assert "token" in response.json()


@pytest.mark.asyncio
async def test_create_token_forbidden_for_user(client: httpx.AsyncClient, regular_user):
    user, token = regular_user
    response = await client.post(
        "/auth/tokens",
        json={"user_id": str(user.id), "ttl_days": 7},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_token_admin_only(client: httpx.AsyncClient, admin_user, regular_user, users_storage):
    admin, admin_token = admin_user
    user, _ = regular_user
    token_info = await create_token_for_user(users_storage, user_id=user.id)

    response = await client.delete(
        f"/auth/tokens/{token_info.token}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_token_forbidden_for_user(client: httpx.AsyncClient, regular_user, users_storage):
    user, token = regular_user
    token_info = await create_token_for_user(users_storage, user_id=user.id)

    response = await client.delete(
        f"/auth/tokens/{token_info.token}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
