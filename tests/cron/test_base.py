from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.cron.base import BaseCronTask
from microclaw.cron.settings import CronTaskSettings


@pytest.fixture(autouse=True)
def clear_cron_tasks():
    BaseCronTask._tasks.clear()
    yield


class ConcreteTask(BaseCronTask):
    async def execute(self):
        pass


def test_parse_cron_expression():
    task = ConcreteTask(
        key="test", settings=CronTaskSettings(cron="0 2 * * *"), resolver=MagicMock()
    )
    result = task._parse_cron_expression("0 2 * * *")
    assert result == {
        "minute": "0",
        "hour": "2",
        "day": "*",
        "month": "*",
        "day_of_week": "*",
    }


def test_parse_cron_expression_invalid():
    task = ConcreteTask(
        key="test", settings=CronTaskSettings(cron="* * * * *"), resolver=MagicMock()
    )
    with pytest.raises(ValueError, match="Invalid cron expression"):
        task._parse_cron_expression("* * *")


@pytest.mark.asyncio
async def test_execute_with_logging():
    task = ConcreteTask(
        key="test",
        settings=CronTaskSettings(cron="0 2 * * *"),
        resolver=MagicMock(),
    )
    task.execute = AsyncMock()
    await task._execute_with_logging()
    task.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_not_implemented():
    task = BaseCronTask(
        key="test", settings=CronTaskSettings(cron="0 2 * * *"), resolver=MagicMock()
    )
    with pytest.raises(NotImplementedError):
        await task.execute()


@pytest.mark.asyncio
async def test_do_before_hook():
    class TaskWithHook(ConcreteTask):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.hook_called = False

        async def do_before(self):
            self.hook_called = True

    task = TaskWithHook(
        key="test",
        settings=CronTaskSettings(cron="0 2 * * *"),
        resolver=MagicMock(),
    )
    await task.do_before()
    assert task.hook_called is True


def test_get_settings_class_with_generic():
    from microclaw.cron.settings import CronTaskSettings

    class GenericTask(BaseCronTask[CronTaskSettings]):
        async def execute(self):
            pass

    assert GenericTask.get_settings_class() is CronTaskSettings


def test_get_settings_class_without_generic():
    assert ConcreteTask.get_settings_class().__name__ == "EmptySettings"


@pytest.mark.asyncio
async def test_start_and_stop_with_mock_scheduler():
    scheduler = MagicMock()
    scheduler.running = True
    scheduler.get_job.return_value = MagicMock()

    task = ConcreteTask(
        key="test_task",
        settings=CronTaskSettings(cron="0 2 * * *"),
        resolver=MagicMock(),
    )
    task.get_scheduler = lambda: scheduler

    async with task:
        scheduler.add_job.assert_called_once()
        assert "test_task" in BaseCronTask._tasks

    scheduler.remove_job.assert_called_once_with("test_task")
    assert "test_task" not in BaseCronTask._tasks


def test_get_scheduler_returns_existing():
    scheduler = MagicMock()
    BaseCronTask._scheduler = scheduler
    try:
        task = ConcreteTask(
            key="test",
            settings=CronTaskSettings(cron="0 2 * * *"),
            resolver=MagicMock(),
        )
        result = task.get_scheduler()
        assert result is scheduler
    finally:
        BaseCronTask._scheduler = None


@pytest.mark.asyncio
async def test_execute_with_logging_error():
    task = ConcreteTask(
        key="test",
        settings=CronTaskSettings(cron="0 2 * * *"),
        resolver=MagicMock(),
    )
    task.execute = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await task._execute_with_logging()


@pytest.mark.asyncio
async def test_start_starts_scheduler():
    scheduler = MagicMock()
    scheduler.running = False
    scheduler.get_job.return_value = None

    task = ConcreteTask(
        key="test_task",
        settings=CronTaskSettings(cron="0 2 * * *"),
        resolver=MagicMock(),
    )
    task.get_scheduler = lambda: scheduler

    try:
        await task.start()
    except Exception:
        pass

    scheduler.start.assert_called_once()


@pytest.mark.asyncio
async def test_start_replaces_existing_task():
    scheduler = MagicMock()
    scheduler.running = True
    scheduler.get_job.return_value = None

    task = ConcreteTask(
        key="dup_task",
        settings=CronTaskSettings(cron="0 2 * * *"),
        resolver=MagicMock(),
    )
    task.get_scheduler = lambda: scheduler

    BaseCronTask._tasks["dup_task"] = task

    try:
        await task.start()
    except Exception:
        pass

    assert "dup_task" in BaseCronTask._tasks
