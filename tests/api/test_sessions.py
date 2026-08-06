import uuid

import httpx
import pytest


@pytest.mark.asyncio
async def test_create_session(client: httpx.AsyncClient, regular_user, users_storage):
    user, token = regular_user
    response = await client.post(
        "/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "id" in data

    sessions = await users_storage.get_user_sessions(
        user.id, "rest", str(user.id)
    )
    assert uuid.UUID(data["id"]) in sessions


@pytest.mark.asyncio
async def test_list_sessions_admin(client: httpx.AsyncClient, admin_user, sessions_storage, users_storage):
    admin, token = admin_user
    sid = await sessions_storage.create_session()
    await users_storage.attach_session_to_user(admin.id, sid, "rest", str(admin.id))

    response = await client.get(
        "/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_list_sessions_forbidden_for_regular(client: httpx.AsyncClient, regular_user):
    _, token = regular_user
    response = await client.get(
        "/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_session(client: httpx.AsyncClient, regular_user, sessions_storage, users_storage):
    user, token = regular_user
    sid = await sessions_storage.create_session()
    await users_storage.attach_session_to_user(user.id, sid, "rest", str(user.id))

    response = await client.get(
        f"/sessions/{sid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(sid)


@pytest.mark.asyncio
async def test_get_session_not_found(client: httpx.AsyncClient, regular_user):
    _, token = regular_user
    response = await client.get(
        f"/sessions/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_session_other_user_forbidden(client: httpx.AsyncClient, admin_user, regular_user, sessions_storage, users_storage):
    admin, admin_token = admin_user
    user, user_token = regular_user
    sid = await sessions_storage.create_session()
    await users_storage.attach_session_to_user(admin.id, sid, "rest", str(admin.id))

    response = await client.get(
        f"/sessions/{sid}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_session(client: httpx.AsyncClient, regular_user, sessions_storage, users_storage):
    user, token = regular_user
    sid = await sessions_storage.create_session()
    await users_storage.attach_session_to_user(user.id, sid, "rest", str(user.id))

    response = await client.delete(
        f"/sessions/{sid}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204
    assert await sessions_storage.get_session(sid) is None


@pytest.mark.asyncio
async def test_delete_session_other_user_forbidden(client: httpx.AsyncClient, admin_user, regular_user, sessions_storage, users_storage):
    admin, _ = admin_user
    _, user_token = regular_user
    sid = await sessions_storage.create_session()
    await users_storage.attach_session_to_user(admin.id, sid, "rest", str(admin.id))

    response = await client.delete(
        f"/sessions/{sid}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_session_spending(client: httpx.AsyncClient, regular_user, sessions_storage, users_storage):
    user, token = regular_user
    sid = await sessions_storage.create_session()
    await users_storage.attach_session_to_user(user.id, sid, "rest", str(user.id))

    response = await client.get(
        f"/sessions/{sid}/spending",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["cost"] == 0.0
