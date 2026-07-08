from unittest.mock import AsyncMock

import pytest

from microclaw.agents.agent import Agent
from microclaw.agents.settings import (
    AgentSettings,
    ModelSettings,
    ProviderSettings,
    APITypeEnum,
)
from microclaw.channels.telegram.base import BaseTelegramChannel
from microclaw.channels.telegram.settings import TelegramSettings
from microclaw.channels.telegram.toolkit import TelegramToolKit
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage
from microclaw.syncers.memory.settings import MemorySyncerSettings
from microclaw.syncers.memory.syncer import MemorySyncer
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage


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


def test_get_toolkit_returns_telegram_toolkit(telegram_channel):
    toolkit = telegram_channel.get_toolkit()
    assert isinstance(toolkit, TelegramToolKit)
    assert toolkit.prefix == "telegram_channel_"
