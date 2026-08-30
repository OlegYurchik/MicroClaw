from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.cron.settings import CronTaskSettings
from microclaw.cron.tasks.flush_to_memory import FlushToMemoryCronTask


@pytest.fixture
def flush_task():
    resolver = MagicMock()
    resolver.resolve_sessions_storages = AsyncMock(
        return_value={"default": MagicMock()}
    )
    resolver.resolve_channels = AsyncMock(return_value={})
    resolver.resolve_agents = AsyncMock(return_value={})

    return FlushToMemoryCronTask(
        key="flush",
        settings=CronTaskSettings(cron="0 2 * * *"),
        resolver=resolver,
    )


@pytest.mark.asyncio
async def test_do_before_resolves_dependencies(flush_task):
    sessions_storage = MagicMock()
    flush_task._resolver.resolve_sessions_storages = AsyncMock(
        return_value={"default": sessions_storage}
    )
    channel = MagicMock()
    flush_task._resolver.resolve_channels = AsyncMock(
        return_value={"telegram": channel}
    )

    await flush_task.do_before()

    assert flush_task._sessions_storage is sessions_storage
    assert flush_task._channels == {"telegram": channel}


@pytest.mark.asyncio
async def test_do_before_no_sessions_storage_raises(flush_task):
    flush_task._resolver.resolve_sessions_storages = AsyncMock(return_value={})
    flush_task._resolver.resolve_channels = AsyncMock(
        return_value={"telegram": MagicMock()}
    )

    with pytest.raises(RuntimeError, match="Sessions storage not found"):
        await flush_task.do_before()


@pytest.mark.asyncio
async def test_do_before_no_channels_raises(flush_task):
    flush_task._resolver.resolve_sessions_storages = AsyncMock(
        return_value={"default": MagicMock()}
    )
    flush_task._resolver.resolve_channels = AsyncMock(return_value={})

    with pytest.raises(RuntimeError, match="No channels found"):
        await flush_task.do_before()


@pytest.mark.asyncio
async def test_execute_no_sessions(flush_task):
    async def empty_gen(**kwargs):
        return
        yield  # unreachable, makes it an async generator

    sessions_storage = MagicMock()
    sessions_storage.get_sessions = empty_gen

    flush_task._sessions_storage = sessions_storage
    flush_task._channels = {"telegram": MagicMock()}
    flush_task._resolver.resolve_agents = AsyncMock(return_value={})

    await flush_task.execute()
