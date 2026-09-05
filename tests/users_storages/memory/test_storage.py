import uuid

import pytest

from microclaw.users_storages.dto import (
    UserChannelCreate,
    UserChannelUpdate,
    UserCreate,
    UserUpdate,
)
from microclaw.users_storages.filters import UserChannelFilter, UserFilter
from tests.users_storages.helpers import (
    assert_cron_crud,
    assert_delete_users_filter,
    assert_pagination_and_sort,
    assert_token_crud,
    assert_user_channel_crud,
    assert_user_crud,
)


@pytest.mark.asyncio
async def test_user_crud(memory_users_storage):
    await assert_user_crud(memory_users_storage)


@pytest.mark.asyncio
async def test_user_channel_crud(memory_users_storage):
    await assert_user_channel_crud(memory_users_storage)


@pytest.mark.asyncio
async def test_token_crud(memory_users_storage):
    await assert_token_crud(memory_users_storage)


@pytest.mark.asyncio
async def test_cron_crud(memory_users_storage):
    await assert_cron_crud(memory_users_storage)


@pytest.mark.asyncio
async def test_pagination_and_sort(memory_users_storage):
    await assert_pagination_and_sort(memory_users_storage)


@pytest.mark.asyncio
async def test_delete_users_filter(memory_users_storage):
    await assert_delete_users_filter(memory_users_storage)


@pytest.mark.asyncio
async def test_attach_session_to_user_sets_actual(memory_users_storage):
    user = await memory_users_storage.create_user(data=UserCreate())
    session_id = uuid.uuid4()
    await memory_users_storage.create_user_channel(
        data=UserChannelCreate(
            user_id=user.id,
            channel_key="tui",
            channel_internal_id="tui",
        )
    )
    async for _ in memory_users_storage.update_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"tui"},
            channel_internal_id={"tui"},
        ),
        data=UserChannelUpdate(actual_session_id=session_id),
    ):
        pass
    actual = None
    async for channel in memory_users_storage.get_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"tui"},
            channel_internal_id={"tui"},
        )
    ):
        actual = channel.actual_session_id
        break
    assert actual == session_id


@pytest.mark.asyncio
async def test_set_actual_session_updates_actual(memory_users_storage):
    user = await memory_users_storage.create_user(data=UserCreate())
    session1 = uuid.uuid4()
    session2 = uuid.uuid4()
    await memory_users_storage.create_user_channel(
        data=UserChannelCreate(
            user_id=user.id,
            channel_key="tui",
            channel_internal_id="tui",
        )
    )
    async for _ in memory_users_storage.update_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"tui"},
            channel_internal_id={"tui"},
        ),
        data=UserChannelUpdate(actual_session_id=session1),
    ):
        pass
    async for _ in memory_users_storage.update_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"tui"},
            channel_internal_id={"tui"},
        ),
        data=UserChannelUpdate(actual_session_id=session2),
    ):
        pass
    actual = None
    async for channel in memory_users_storage.get_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"tui"},
            channel_internal_id={"tui"},
        )
    ):
        actual = channel.actual_session_id
        break
    assert actual == session2


@pytest.mark.asyncio
async def test_update_user_agent(memory_users_storage):
    user = await memory_users_storage.create_user(data=UserCreate())
    updated = None
    async for u in memory_users_storage.update_users(
        filter_=UserFilter(id={user.id}),
        data=UserUpdate(agent={"model": "test_agent"}),
    ):
        updated = u
    assert updated is not None
    assert updated.agent == {"model": "test_agent"}
    fetched = await memory_users_storage.get_user(filter_=UserFilter(id={user.id}))
    assert fetched.agent == {"model": "test_agent"}


@pytest.mark.asyncio
async def test_multiple_sessions_only_one_actual(memory_users_storage):
    user = await memory_users_storage.create_user(data=UserCreate())
    s1 = uuid.uuid4()
    s2 = uuid.uuid4()
    await memory_users_storage.create_user_channel(
        data=UserChannelCreate(
            user_id=user.id,
            channel_key="tui",
            channel_internal_id="tui",
        )
    )
    async for _ in memory_users_storage.update_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"tui"},
            channel_internal_id={"tui"},
        ),
        data=UserChannelUpdate(actual_session_id=s1),
    ):
        pass
    async for _ in memory_users_storage.update_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"tui"},
            channel_internal_id={"tui"},
        ),
        data=UserChannelUpdate(actual_session_id=s2),
    ):
        pass
    actual = None
    async for channel in memory_users_storage.get_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"tui"},
            channel_internal_id={"tui"},
        )
    ):
        actual = channel.actual_session_id
        break
    assert actual == s2
