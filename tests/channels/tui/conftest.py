from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio

from microclaw.agents.settings import AgentIdentity, AgentSettings
from microclaw.channels.tui.channel import TUIChannel
from microclaw.channels.tui.settings import TUIChannelSettings
from microclaw.users_storages.dto import UserCreate


@pytest_asyncio.fixture
async def tui_channel(agent, sessions_storage, syncer, users_storage):
    settings = TUIChannelSettings()
    resolver = MagicMock()
    resolver.settings.agents = {
        "default": AgentSettings(
            identity=AgentIdentity(name="DefaultAgent"),
        ),
        "other": AgentSettings(
            identity=AgentIdentity(name="OtherAgent"),
        ),
    }
    resolver.resolve_agent = AsyncMock(return_value=agent)

    channel = TUIChannel(
        settings=settings,
        agent=agent,
        sessions_storage=sessions_storage,
        syncer=syncer,
        users_storage=users_storage,
        resolver=resolver,
        channel_key="tui",
    )
    # Mock the textual app to avoid needing an event loop
    channel._app = MagicMock()
    channel._app.chat_widget = MagicMock()

    # Initialize user that start() would normally create, without running the app
    user = await users_storage.create_user(data=UserCreate())
    object.__setattr__(channel, "_user", user)

    return channel
