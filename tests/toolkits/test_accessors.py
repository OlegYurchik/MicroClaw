from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from microclaw.dto import AgentMessage
from microclaw.toolkits.accessors.session import (
    AllSessionsAccessor,
    CurrentSessionAccessor,
    UserSessionsAccessor,
)
from microclaw.toolkits.accessors.user import AllUsersAccessor, CurrentUserAccessor
from microclaw.users_storages.dto import UserChannelCreate


@pytest.mark.asyncio
async def test_current_user_accessor_read_only():
    storage = MagicMock()
    storage.get_user = AsyncMock(return_value=None)
    acc = CurrentUserAccessor(user_id=uuid.uuid4(), storage=storage, writable=False)
    await acc.get()
    storage.get_user.assert_awaited_once()
    with pytest.raises(PermissionError):
        await acc.update_agent_settings(None)


@pytest.mark.asyncio
async def test_current_user_accessor_writable():
    storage = MagicMock()
    storage.update_user = AsyncMock(return_value=MagicMock())
    invalidate = MagicMock()
    acc = CurrentUserAccessor(
        user_id=uuid.uuid4(),
        storage=storage,
        writable=True,
        invalidate_cache=invalidate,
    )
    await acc.update_agent_settings(None)
    storage.update_user.assert_awaited_once()
    invalidate.assert_called_once()


@pytest.mark.asyncio
async def test_user_sessions_accessor():

    storage = MagicMock()
    storage.get_user_channel = AsyncMock(
        return_value=UserChannelCreate(
            user_id=uuid.uuid4(),
            channel_key="telegram",
            channel_internal_id="12345",
            actual_session_id=uuid.uuid4(),
        )
    )
    acc = UserSessionsAccessor(user_id=uuid.uuid4(), storage=storage)
    sessions = await acc.get_user_sessions("telegram", "12345")
    storage.get_user_channel.assert_awaited_once()
    assert len(sessions) == 1


@pytest.mark.asyncio
async def test_all_users_accessor():
    storage = MagicMock()
    storage.get_user_channels = MagicMock(return_value=_async_gen([]))
    acc = AllUsersAccessor(storage=storage)
    result = await acc.get_by_session(uuid.uuid4())
    storage.get_user_channels.assert_called_once()
    assert result is None


def _async_gen(items):
    async def _gen():
        for item in items:
            yield item
    return _gen()


async def _mock_get_crons(*args, **kwargs):
    return
    yield

@pytest.mark.asyncio
async def test_all_users_accessor_crons_read_only():
    storage = MagicMock()
    storage.get_crons = MagicMock(side_effect=_mock_get_crons)
    acc = AllUsersAccessor(storage=storage, writable=False)
    result = await acc.get_crons(uuid.uuid4())
    storage.get_crons.assert_called_once()
    assert result == []


@pytest.mark.asyncio
async def test_all_users_accessor_crons_writable():
    storage = MagicMock()
    storage.create_cron = AsyncMock()
    storage.delete_cron = AsyncMock()
    acc = AllUsersAccessor(storage=storage, writable=True)
    user_id = uuid.uuid4()
    cron = MagicMock()
    cron.id = uuid.uuid4()
    cron.path = "test.path"
    cron.cron = "*/5 * * * *"
    cron.enabled = True
    cron.args = {}
    await acc.create_cron(user_id, cron)
    storage.create_cron.assert_awaited_once()
    cron_id = uuid.uuid4()
    await acc.remove_cron(cron_id)
    storage.delete_cron.assert_awaited_once()


@pytest.mark.asyncio
async def test_all_users_accessor_crons_not_writable_raises():
    storage = MagicMock()
    acc = AllUsersAccessor(storage=storage, writable=False)
    with pytest.raises(PermissionError):
        await acc.create_cron(uuid.uuid4(), MagicMock())
    with pytest.raises(PermissionError):
        await acc.remove_cron(uuid.uuid4())


@pytest.mark.asyncio
async def test_current_session_accessor_read_only():
    storage = MagicMock()
    storage.get_messages.return_value = []
    acc = CurrentSessionAccessor(
        session_id=uuid.uuid4(), storage=storage, writable=False
    )
    result = acc.get_messages()
    storage.get_messages.assert_called_once()
    assert result == []
    with pytest.raises(PermissionError):
        await acc.add_message(MagicMock())


@pytest.mark.asyncio
async def test_current_session_accessor_writable():
    storage = MagicMock()
    storage.create_message = AsyncMock()
    acc = CurrentSessionAccessor(
        session_id=uuid.uuid4(), storage=storage, writable=True
    )
    await acc.add_message(AgentMessage(role="user"))
    storage.create_message.assert_awaited_once()


async def _mock_get_sessions(*args, **kwargs):
    return
    yield

@pytest.mark.asyncio
async def test_all_sessions_accessor():
    storage = MagicMock()
    storage.get_sessions = MagicMock(side_effect=_mock_get_sessions)
    acc = AllSessionsAccessor(storage=storage)
    result = [s async for s in acc.get_sessions()]
    storage.get_sessions.assert_called_once()
    assert result == []
