import uuid

import httpx
import pytest

from microclaw.sessions_storages.dto import SessionCreate
from microclaw.sessions_storages.filters import SessionFilter
from microclaw.users_storages.filters import UserChannelFilter
from microclaw.users_storages.utils import attach_session_to_user


@pytest.mark.asyncio
async def test_create_session(client: httpx.AsyncClient, regular_user, users_storage):
    user, token = regular_user
    response = await client.post(
        "/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data

    channels = []
    async for channel in users_storage.get_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"rest"},
            channel_internal_id={str(user.id)},
        )
    ):
        channels.append(channel)
    assert len(channels) == 1
    assert uuid.UUID(data["id"]) == channels[0].actual_session_id


@pytest.mark.asyncio
async def test_create_session_sets_actual(
    client: httpx.AsyncClient, regular_user, users_storage
):
    user, token = regular_user
    response = await client.post(
        "/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    session_id = uuid.UUID(data["id"])
    channels = []
    async for channel in users_storage.get_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"rest"},
            channel_internal_id={str(user.id)},
        )
    ):
        channels.append(channel)
    assert len(channels) == 1
    assert channels[0].actual_session_id == session_id


@pytest.mark.asyncio
async def test_list_sessions_admin(
    client: httpx.AsyncClient, admin_user, session_factory
):
    admin, token = admin_user
    await session_factory(admin)

    response = await client.get(
        "/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) >= 1


@pytest.mark.asyncio
async def test_list_sessions_forbidden_for_regular(
    client: httpx.AsyncClient, regular_user
):
    _, token = regular_user
    response = await client.get(
        "/sessions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_session(client: httpx.AsyncClient, regular_user, sessions_storage, users_storage):
    user, token = regular_user
    session_id = (await sessions_storage.create_session(
        data=SessionCreate(channel_key="rest", channel_internal_id=str(user.id))
    )).id
    await attach_session_to_user(users_storage, user.id, session_id, "rest", str(user.id))

    response = await client.get(
        f"/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(session_id)


@pytest.mark.asyncio
async def test_get_session_not_found(client: httpx.AsyncClient, regular_user):
    _, token = regular_user
    response = await client.get(
        f"/sessions/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_session_other_user_forbidden(
    client: httpx.AsyncClient, admin_user, regular_user, sessions_storage, users_storage
):
    admin, admin_token = admin_user
    user, user_token = regular_user
    session_id = (await sessions_storage.create_session(
        data=SessionCreate(channel_key="rest", channel_internal_id=str(admin.id))
    )).id
    await attach_session_to_user(users_storage, admin.id, session_id, "rest", str(admin.id))

    response = await client.get(
        f"/sessions/{session_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_session(
    client: httpx.AsyncClient, regular_user, sessions_storage, users_storage
):
    user, token = regular_user
    session_id = (await sessions_storage.create_session(
        data=SessionCreate(channel_key="rest", channel_internal_id=str(user.id))
    )).id
    await attach_session_to_user(users_storage, user.id, session_id, "rest", str(user.id))

    response = await client.delete(
        f"/sessions/{session_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204
    assert await sessions_storage.get_session(filter_=SessionFilter(id={session_id})) is None


@pytest.mark.asyncio
async def test_delete_session_other_user_forbidden(
    client: httpx.AsyncClient, admin_user, regular_user, sessions_storage, users_storage
):
    admin, _ = admin_user
    _, user_token = regular_user
    session_id = (await sessions_storage.create_session(
        data=SessionCreate(channel_key="rest", channel_internal_id=str(admin.id))
    )).id
    await attach_session_to_user(users_storage, admin.id, session_id, "rest", str(admin.id))

    response = await client.delete(
        f"/sessions/{session_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_session_spending(
    client: httpx.AsyncClient, regular_user, sessions_storage, users_storage
):
    user, token = regular_user
    session_id = (await sessions_storage.create_session(
        data=SessionCreate(channel_key="rest", channel_internal_id=str(user.id))
    )).id
    await attach_session_to_user(users_storage, user.id, session_id, "rest", str(user.id))

    response = await client.get(
        f"/sessions/{session_id}/spending",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["cost"] == 0.0
