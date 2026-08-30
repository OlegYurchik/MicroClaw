from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.cron.settings import CronTaskSettings
from microclaw.cron.tasks.agent import AgentCronTask


def _async_gen(items):
    async def _gen():
        for item in items:
            yield item

    return _gen()


@pytest.fixture
def cron_task_settings() -> CronTaskSettings:
    return CronTaskSettings(
        path="microclaw.cron.tasks.agent.AgentCronTask",
        cron="0 4 * * *",
        args={"task": "default"},
    )


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.ask = MagicMock(return_value=_async_gen([]))
    agent.has_pending_interrupt = AsyncMock(return_value=False)
    agent.is_summarization_enabled.return_value = False
    agent.toolkits = {}
    return agent


@pytest.fixture
def agent_cron_task(
    cron_task_settings: CronTaskSettings,
    resolver: AsyncMock,
    base_channel,
    mock_agent,
) -> AgentCronTask:
    resolver.resolve_channels = AsyncMock(return_value={"tui": base_channel})
    resolver.resolve_agents = AsyncMock(return_value={"default": mock_agent})

    task = AgentCronTask(
        key="morning_briefing",
        settings=cron_task_settings,
        resolver=resolver,
    )
    return task


@pytest.fixture
def make_agent_cron_task(resolver: AsyncMock, base_channel, mock_agent):
    def _make(args: dict | None = None):
        resolver.resolve_channels = AsyncMock(return_value={"tui": base_channel})
        resolver.resolve_agents = AsyncMock(return_value={"default": mock_agent})
        settings = CronTaskSettings(
            path="microclaw.cron.tasks.agent.AgentCronTask",
            cron="0 4 * * *",
            args=args or {"task": "default"},
        )
        return AgentCronTask(
            key="morning_briefing",
            settings=settings,
            resolver=resolver,
        )

    return _make
