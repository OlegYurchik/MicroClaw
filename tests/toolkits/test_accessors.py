import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.toolkits.accessors.session import (
    AllSessionsAccessor,
    CurrentSessionAccessor,
    UserSessionsAccessor,
)
from microclaw.toolkits.accessors.user import AllUsersAccessor, CurrentUserAccessor


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
    storage.get_user_sessions = AsyncMock(return_value=[uuid.uuid4()])
    acc = UserSessionsAccessor(user_id=uuid.uuid4(), storage=storage)
    sessions = await acc.get_user_sessions("telegram", "12345")
    storage.get_user_sessions.assert_awaited_once()
    assert len(sessions) == 1


@pytest.mark.asyncio
async def test_all_users_accessor():
    storage = MagicMock()
    storage.get_user_by_session = AsyncMock(return_value=None)
    acc = AllUsersAccessor(storage=storage)
    result = await acc.get_by_session(uuid.uuid4())
    storage.get_user_by_session.assert_awaited_once()
    assert result is None


@pytest.mark.asyncio
async def test_all_users_accessor_crons_read_only():
    storage = MagicMock()
    storage.get_crons = AsyncMock(return_value=[])
    acc = AllUsersAccessor(storage=storage, writable=False)
    result = await acc.get_crons(uuid.uuid4())
    storage.get_crons.assert_awaited_once()
    assert result == []


@pytest.mark.asyncio
async def test_all_users_accessor_crons_writable():
    storage = MagicMock()
    storage.create_cron = AsyncMock()
    storage.remove_cron = AsyncMock()
    acc = AllUsersAccessor(storage=storage, writable=True)
    user_id = uuid.uuid4()
    cron = MagicMock()
    await acc.create_cron(user_id, cron)
    storage.create_cron.assert_awaited_once()
    cron_id = uuid.uuid4()
    await acc.remove_cron(cron_id)
    storage.remove_cron.assert_awaited_once()


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
    storage.add_message = AsyncMock()
    acc = CurrentSessionAccessor(
        session_id=uuid.uuid4(), storage=storage, writable=True
    )
    await acc.add_message(MagicMock())
    storage.add_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_all_sessions_accessor():
    storage = MagicMock()
    storage.get_sessions.return_value = []
    acc = AllSessionsAccessor(storage=storage)
    result = acc.get_sessions()
    storage.get_sessions.assert_called_once()
    assert result == []
