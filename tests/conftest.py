from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.agents.agent import Agent
from microclaw.agents.settings import (
    AgentSettings,
    APITypeEnum,
    ModelCosts,
    ModelSettings,
    ProviderSettings,
)
from microclaw.channels.settings import ChannelSettings, ChannelTypeEnum
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage
from microclaw.syncers.memory.settings import MemorySyncerSettings
from microclaw.syncers.memory.syncer import MemorySyncer
from microclaw.toolkits.base import BaseToolKit
from microclaw.toolkits.memory import MemoryToolKit
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage


@pytest.fixture
def agent_settings() -> AgentSettings:
    return AgentSettings()


@pytest.fixture
def provider_settings() -> ProviderSettings:
    return ProviderSettings(
        base_url="http://localhost:11434",
        api_type=APITypeEnum.OLLAMA,
    )


@pytest.fixture
def model_settings() -> ModelSettings:
    return ModelSettings(
        id="gpt-4",
        costs=ModelCosts(input=1, output=2, currency="$"),
    )


@pytest.fixture
def toolkit() -> MagicMock:
    toolkit = MagicMock(spec=BaseToolKit)
    toolkit.get_tools.return_value = []
    return toolkit


@pytest.fixture
def memory_toolkit() -> MagicMock:
    toolkit = MagicMock(spec=MemoryToolKit)
    toolkit.get_tools.return_value = []
    toolkit.get_memory = AsyncMock(return_value="general memory")
    return toolkit


@pytest.fixture
def toolkits(toolkit, memory_toolkit) -> dict[str, BaseToolKit]:
    return {
        "tools": toolkit,
        "memory": memory_toolkit,
    }


@pytest.fixture
def client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def channel() -> MagicMock:
    channel = MagicMock()
    channel_toolkit = MagicMock()
    channel_toolkit.get_tools.return_value = []
    channel.get_toolkit.return_value = channel_toolkit
    return channel


@pytest.fixture
def agent(
    agent_settings, model_settings, provider_settings, toolkits, client, syncer
) -> Agent:
    return Agent(
        settings=agent_settings,
        model_settings=model_settings,
        provider_settings=provider_settings,
        toolkits=toolkits,
        syncer=syncer,
        mcp_settings={},
        client=client,
    )


@pytest.fixture
def make_agent(agent_settings, model_settings, provider_settings, syncer):
    def _make(toolkits, client=None, **extra):
        return Agent(
            settings=agent_settings,
            model_settings=model_settings,
            provider_settings=provider_settings,
            toolkits=toolkits,
            syncer=syncer,
            mcp_settings={},
            client=client,
            **extra,
        )

    return _make


@pytest.fixture
def channel_settings() -> ChannelSettings:
    return ChannelSettings(type=ChannelTypeEnum.CLI)


@pytest.fixture
def sessions_storage() -> MemorySessionsStorage:
    return MemorySessionsStorage(settings=MemorySessionsStorageSettings())


@pytest.fixture
def syncer() -> MemorySyncer:
    return MemorySyncer(settings=MemorySyncerSettings())


@pytest.fixture
def users_storage() -> MemoryUsersStorage:
    return MemoryUsersStorage(settings=MemoryUsersStorageSettings())


@pytest.fixture
def resolver() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def base_channel(
    channel_settings, agent, sessions_storage, syncer, users_storage, resolver
):
    from tests.factories import FakeChannel

    return FakeChannel(
        settings=channel_settings,
        agent=agent,
        sessions_storage=sessions_storage,
        syncer=syncer,
        users_storage=users_storage,
        resolver=resolver,
    )
