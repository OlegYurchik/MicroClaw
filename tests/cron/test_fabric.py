from unittest.mock import MagicMock

import pytest

from microclaw.cron.fabric import get_cron_task
from microclaw.cron.settings import CronTaskSettings
from microclaw.cron.tasks.flush_to_memory import FlushToMemoryCronTask


@pytest.mark.asyncio
async def test_get_cron_task_success():
    settings = CronTaskSettings(
        path="microclaw.cron.tasks.flush_to_memory.FlushToMemoryCronTask",
        cron="0 2 * * *",
    )
    result = await get_cron_task("flush", settings=settings, resolver=MagicMock())
    assert isinstance(result, FlushToMemoryCronTask)


@pytest.mark.asyncio
async def test_get_cron_task_not_found():
    settings = CronTaskSettings(
        path="microclaw.cron.tasks.flush_to_memory.NonExistentClass",
        cron="0 2 * * *",
    )
    with pytest.raises(AttributeError):
        await get_cron_task("flush", settings=settings, resolver=MagicMock())


@pytest.mark.asyncio
async def test_get_cron_task_not_callable():
    settings = CronTaskSettings(
        path="microclaw.cron.tasks.flush_to_memory.datetime",
        cron="0 2 * * *",
    )
    with pytest.raises(TypeError):
        await get_cron_task("flush", settings=settings, resolver=MagicMock())


@pytest.mark.asyncio
async def test_get_cron_task_not_subclass():
    settings = CronTaskSettings(
        path="microclaw.cron.settings.CronTaskSettings",
        cron="0 2 * * *",
    )
    with pytest.raises(ValueError, match="not a subclass of BaseCronTask"):
        await get_cron_task("flush", settings=settings, resolver=MagicMock())
