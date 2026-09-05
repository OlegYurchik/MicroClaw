from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from microclaw.channels.tui.channel import TUIChannel
from microclaw.channels.tui.settings import TUIChannelSettings
from microclaw.dto import AgentMessage, AgentMessageRoleEnum


class TestTUIChannel:
    @pytest.fixture
    def tui_settings(self):
        return TUIChannelSettings(type="tui")

    @pytest.fixture
    def app(self):
        app = MagicMock()
        app.chat_widget = MagicMock()
        app.clear_messages = AsyncMock()
        app.clear_queued_messages = AsyncMock()
        app.set_queued_messages = AsyncMock()
        app.add_message = AsyncMock()
        app.run_async = AsyncMock()
        return app

    @pytest.fixture
    def channel(
        self,
        tui_settings,
        agent,
        sessions_storage,
        syncer,
        users_storage,
        resolver,
        app,
    ):
        channel = TUIChannel(
            settings=tui_settings,
            agent=agent,
            sessions_storage=sessions_storage,
            syncer=syncer,
            users_storage=users_storage,
            resolver=resolver,
        )
        channel._app = app
        return channel

    @pytest.mark.asyncio
    async def test_handle_new_session(self, channel, app, users_storage):
        from microclaw.users_storages.dto import UserCreate

        user = await users_storage.create_user(data=UserCreate())
        channel._user = user
        await channel.handle_new_session(123)

    @pytest.mark.asyncio
    async def test_on_agent_message_appends_to_widget(self, channel, app):
        msg = AgentMessage(role=AgentMessageRoleEnum.ASSISTANT, text="hello")
        printer = MagicMock()
        printer.register_new_message = AsyncMock()
        channel._printers["123"] = printer
        await channel._on_agent_message(123, uuid.uuid4(), channel._agent, msg)
        printer.register_new_message.assert_awaited()

    @pytest.mark.asyncio
    async def test_on_confirmation_request(self, channel):
        printer = MagicMock()
        printer._send_confirmation = AsyncMock()
        channel._printers["123"] = printer
        await channel._on_confirmation_request(
            123, uuid.uuid4(), channel._agent, [{"description": "test"}]
        )
        printer._send_confirmation.assert_awaited()

    @pytest.mark.asyncio
    async def test_send_system_message(self, channel, app):
        await channel._send_system_message("123", "hello")
        app.add_message.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_toolkit_returns_none(self, channel):
        toolkit = channel.get_toolkit()
        assert toolkit is None

    @pytest.mark.asyncio
    async def test_app_property(self, channel, app):
        assert channel.app is app

    @pytest.mark.asyncio
    async def test_slash_commands(self, channel):
        cmds = channel.slash_commands
        assert isinstance(cmds, list)

    @pytest.mark.asyncio
    async def test_start_creates_user(self, channel, app, users_storage):
        channel.add_task = MagicMock()
        await channel.start()
        assert channel._user is not None

    @pytest.mark.asyncio
    async def test_handle_user_message(self, channel, app, users_storage):
        from microclaw.users_storages.dto import UserCreate

        user = await users_storage.create_user(data=UserCreate())
        channel._user = user
        channel._processing_lock = MagicMock()
        channel._processing_lock.locked = MagicMock(return_value=False)
        channel._enqueue_and_process = AsyncMock()
        await channel.handle_user_message("hello")
        channel._enqueue_and_process.assert_awaited()
