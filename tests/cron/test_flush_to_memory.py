import datetime
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from microclaw.cron.settings import CronTaskSettings
from microclaw.cron.tasks.flush_to_memory import FlushToMemoryCronTask
from microclaw.dto import AgentMessage, AgentMessageRoleEnum


class FakeSession:
    def __init__(self, session_id=None, channel_key="test", channel_internal_id="123"):
        self.id = session_id or uuid.uuid4()
        self.channel_key = channel_key
        self.channel_internal_id = channel_internal_id
        self.created_at = datetime.datetime.now(datetime.timezone.utc)


class FakeUser:
    def __init__(self, user_id=None):
        self.id = user_id or uuid.uuid4()


class FakeUserChannel:
    def __init__(self, user_id):
        self.user_id = user_id


@pytest.fixture
def resolver():
    r = MagicMock()
    r.resolve_sessions_storages = AsyncMock(return_value={"default": MagicMock()})
    r.resolve_channels = AsyncMock(return_value={"default": MagicMock()})
    r.resolve_agents = AsyncMock(return_value={"default": MagicMock()})
    return r


@pytest.fixture
def task(resolver):
    settings = CronTaskSettings(
        path="microclaw.cron.tasks.flush_to_memory.FlushToMemoryCronTask",
        cron="0 0 * * *",
        enabled=True,
    )
    return FlushToMemoryCronTask(key="flush", settings=settings, resolver=resolver)


@pytest.mark.asyncio
async def test_do_before_raises_without_storage(task):
    task._resolver.resolve_sessions_storages = AsyncMock(return_value={})
    with pytest.raises(RuntimeError, match="Sessions storage not found"):
        await task.do_before()


@pytest.mark.asyncio
async def test_do_before_raises_without_channels(task):
    task._resolver.resolve_sessions_storages = AsyncMock(
        return_value={"default": MagicMock()}
    )
    task._resolver.resolve_channels = AsyncMock(return_value={})
    with pytest.raises(RuntimeError, match="No channels found"):
        await task.do_before()


async def _empty_async_gen():
    return
    yield  # Make it an async generator


async def _single_item_gen(item):
    yield item


@pytest.mark.asyncio
async def test_execute_no_sessions(task, resolver):
    sessions_storage = MagicMock()
    sessions_storage.get_sessions = MagicMock(return_value=_empty_async_gen())

    resolver.resolve_sessions_storages = AsyncMock(
        return_value={"default": sessions_storage}
    )
    channel = MagicMock()
    resolver.resolve_channels = AsyncMock(return_value={"default": channel})

    await task.do_before()
    await task.execute()


@pytest.mark.asyncio
async def test_process_day_user_not_found(task, resolver):
    session = FakeSession()
    sessions_storage = MagicMock()
    sessions_storage.get_sessions = MagicMock(return_value=_single_item_gen(session))

    channel = MagicMock()
    users_storage = MagicMock()
    users_storage.get_user_channels = MagicMock(return_value=_empty_async_gen())
    channel.get_users_storage = MagicMock(return_value=users_storage)

    resolver.resolve_sessions_storages = AsyncMock(
        return_value={"default": sessions_storage}
    )
    resolver.resolve_channels = AsyncMock(return_value={"default": channel})

    await task.do_before()
    await task._process_day(datetime.date.today())


@pytest.mark.asyncio
async def test_process_day_full_flow(task, resolver):
    user = FakeUser()
    session = FakeSession()
    sessions_storage = MagicMock()
    sessions_storage.get_sessions = MagicMock(return_value=_single_item_gen(session))
    sessions_storage.get_messages = MagicMock(
        return_value=_single_item_gen(
            AgentMessage(role=AgentMessageRoleEnum.USER, text="hello")
        )
    )

    users_storage = MagicMock()
    users_storage.get_user_channels = MagicMock(
        return_value=_single_item_gen(FakeUserChannel(user.id))
    )
    users_storage.get_user = AsyncMock(return_value=user)

    agent = MagicMock()
    agent.extract_important_info = AsyncMock(return_value="important info")
    agent.summarize_memory = AsyncMock(return_value=MagicMock(content="summary"))

    memory_toolkit = MagicMock()
    memory_toolkit.get_memory = AsyncMock(return_value="")
    memory_toolkit.append_to_memory = AsyncMock()
    agent.get_memory_toolkit = MagicMock(return_value=memory_toolkit)

    channel = MagicMock()
    channel.get_users_storage = MagicMock(return_value=users_storage)
    channel.get_agent_for_user = AsyncMock(return_value=agent)

    resolver.resolve_sessions_storages = AsyncMock(
        return_value={"default": sessions_storage}
    )
    resolver.resolve_channels = AsyncMock(return_value={"default": channel})
    resolver.resolve_agents = AsyncMock(return_value={"default": agent})

    await task.do_before()
    await task._process_day(datetime.date.today())
    memory_toolkit.append_to_memory.assert_awaited()
