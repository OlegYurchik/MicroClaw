from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.agents.agent import Agent
from microclaw.agents.settings import (
    AgentSettings,
    APITypeEnum,
    ModelSettings,
    ProviderSettings,
)
from microclaw.channels.telegram.base import BaseTelegramChannel
from microclaw.channels.telegram.settings import TelegramSettings
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage
from microclaw.syncers.memory.settings import MemorySyncerSettings
from microclaw.syncers.memory.syncer import MemorySyncer
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage


def _async_gen(items):
    async def _gen():
        for item in items:
            yield item

    return _gen()


@pytest.fixture
def telegram_settings() -> TelegramSettings:
    return TelegramSettings(
        token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        allow_from=[],
    )


@pytest.fixture
def telegram_agent() -> Agent:
    return Agent(
        settings=AgentSettings(),
        model_settings=ModelSettings(id="gpt-4"),
        provider_settings=ProviderSettings(
            base_url="http://localhost:11434",
            api_type=APITypeEnum.OLLAMA,
        ),
        toolkits={},
        syncer=MemorySyncer(settings=MemorySyncerSettings()),
        mcp_settings={},
        client=AsyncMock(),
    )


@pytest.fixture
def telegram_channel(telegram_settings, telegram_agent) -> BaseTelegramChannel:
    return BaseTelegramChannel(
        settings=telegram_settings,
        agent=telegram_agent,
        sessions_storage=MemorySessionsStorage(
            settings=MemorySessionsStorageSettings()
        ),
        syncer=MemorySyncer(settings=MemorySyncerSettings()),
        users_storage=MemoryUsersStorage(settings=MemoryUsersStorageSettings()),
        resolver=AsyncMock(),
    )


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.has_pending_interrupt = AsyncMock(return_value=False)
    agent.ask = MagicMock(return_value=_async_gen([]))
    agent.resume_after_confirmation = MagicMock(return_value=_async_gen([]))
    return agent


@pytest.fixture
def make_channel(
    channel_settings,
    sessions_storage,
    syncer,
    users_storage,
    resolver,
    mock_agent,
):
    def _make(agent=None, process_batch_callback=None, chat_sessions=None):
        from tests.factories import FakeChannel

        return FakeChannel(
            settings=channel_settings,
            agent=agent or mock_agent,
            sessions_storage=sessions_storage,
            syncer=syncer,
            users_storage=users_storage,
            resolver=resolver,
            process_batch_callback=process_batch_callback,
            chat_sessions=chat_sessions,
        )

    return _make
