from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from microclaw.channels.tui.channel import TUIChannel
from microclaw.channels.tui.settings import TUIChannelSettings
from microclaw.channels.tui.ui import TUIApp
from microclaw.dto import AgentMessage, AgentMessageRoleEnum
from microclaw.users_storages.dto import UserCreate


class FakeTUIApp(TUIApp):
    def __init__(self, channel=None):
        object.__init__(self)
        self._channel = channel
        self._chat_widget = MagicMock()
        self.exit = MagicMock()
        self.clear_messages = MagicMock()
        self.clear_queued_messages = MagicMock()
        self.add_message = AsyncMock()
        self.set_queued_messages = AsyncMock()
        self.update_message = MagicMock()
        self.push_screen = MagicMock()
        self.run_async = AsyncMock()
        self.show_thinking = MagicMock()
        self.hide_thinking = MagicMock()


@pytest.fixture
def tui_channel(agent, sessions_storage, syncer, users_storage, resolver):
    settings = TUIChannelSettings()
    app = FakeTUIApp(channel=None)
    channel = TUIChannel(
        settings=settings,
        agent=agent,
        sessions_storage=sessions_storage,
        syncer=syncer,
        users_storage=users_storage,
        resolver=resolver,
    )
    channel._app = app
    return channel


@pytest.mark.asyncio
async def test_properties(tui_channel):
    assert isinstance(tui_channel.app, TUIApp)
    assert len(tui_channel.slash_commands) == 1
    assert tui_channel.user is None


@pytest.mark.asyncio
async def test_handle_user_message_slash_exit(tui_channel, users_storage):
    user = await users_storage.create_user(data=UserCreate())
    tui_channel._user = user
    tui_channel._enqueue_and_process = AsyncMock()
    await tui_channel.handle_user_message("/exit")
    tui_channel.app.add_message.assert_awaited()
    tui_channel.app.exit.assert_called_once()
    tui_channel._enqueue_and_process.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_user_message_normal(tui_channel, users_storage):
    user = await users_storage.create_user(data=UserCreate())
    tui_channel._user = user
    tui_channel._enqueue_and_process = AsyncMock()
    await tui_channel.handle_user_message("hello")
    tui_channel.app.add_message.assert_awaited()
    tui_channel._enqueue_and_process.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_user_message_queued_when_locked(tui_channel, users_storage):
    user = await users_storage.create_user(data=UserCreate())
    tui_channel._user = user
    tui_channel._processing_lock = MagicMock()
    tui_channel._processing_lock.locked.return_value = True
    tui_channel._enqueue_and_process = AsyncMock()
    await tui_channel.handle_user_message("hello")
    tui_channel.app.set_queued_messages.assert_awaited_once()
    # MagicMock lock allows async with, so _enqueue_and_process is still called
    tui_channel._enqueue_and_process.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_confirmation_callback(tui_channel):
    tui_channel._process_batch = AsyncMock()
    session_id = uuid.uuid4()
    await tui_channel._handle_confirmation_callback(session_id, approved=True)
    tui_channel._process_batch.assert_awaited_once()
    call_kwargs = tui_channel._process_batch.call_args.kwargs
    assert call_kwargs["session_id"] == session_id
    assert call_kwargs["decision"].value == "approve"


@pytest.mark.asyncio
async def test_on_processing_context_manager(tui_channel):
    session_id = uuid.uuid4()
    agent = MagicMock()
    agent.name = "Test"
    tui_channel._printers = {}
    async with tui_channel._on_processing("chat1", session_id, agent):
        pass
    assert str(session_id) not in tui_channel._printers


@pytest.mark.asyncio
async def test_on_agent_message(tui_channel):
    printer = MagicMock()
    printer.register_new_message = AsyncMock()
    tui_channel._printers["chat1"] = printer
    session_id = uuid.uuid4()
    agent = MagicMock()
    msg = AgentMessage(role=AgentMessageRoleEnum.ASSISTANT, text="hi")
    await tui_channel._on_agent_message("chat1", session_id, agent, msg)
    printer.register_new_message.assert_awaited_once_with(msg)


@pytest.mark.asyncio
async def test_on_confirmation_request(tui_channel):
    printer = MagicMock()
    printer._send_confirmation = AsyncMock()
    tui_channel._printers["chat1"] = printer
    session_id = uuid.uuid4()
    agent = MagicMock()
    await tui_channel._on_confirmation_request(
        "chat1", session_id, agent, [{"text": "ok?"}]
    )
    printer._send_confirmation.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_system_message(tui_channel):
    await tui_channel._send_system_message("chat1", "sys msg")
    tui_channel.app.add_message.assert_awaited_once()
    call_args = tui_channel.app.add_message.await_args
    assert call_args.kwargs["text"] == "sys msg"


@pytest.mark.asyncio
async def test_print_spent_no_user(tui_channel):
    await tui_channel.print_spent()
    # no error
