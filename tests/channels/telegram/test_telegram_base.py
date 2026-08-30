from unittest.mock import AsyncMock, MagicMock
import uuid

import aiogram
import pytest

from microclaw.channels.telegram.base import (
    BaseTelegramChannel,
    ConfirmationCallbackData,
)
from microclaw.channels.telegram.settings import TelegramSettings
from microclaw.channels.telegram.toolkit import TelegramToolKit
from microclaw.dto import AgentMessage, AgentMessageRoleEnum


class FakeTelegramChannel(BaseTelegramChannel):
    async def listen_events(self):
        pass


class TestBaseTelegramChannel:
    @pytest.fixture
    def telegram_settings(self):
        return TelegramSettings(token="test_token", type="telegram", method="polling")

    @pytest.fixture
    def bot(self):
        return AsyncMock(spec=aiogram.Bot)

    @pytest.fixture
    def dispatcher(self):
        dispatcher = MagicMock(spec=aiogram.Dispatcher)
        dispatcher.message = MagicMock()
        dispatcher.message.middleware = MagicMock()
        dispatcher.callback_query = MagicMock()
        dispatcher.callback_query = MagicMock()
        return dispatcher

    @pytest.fixture
    def channel(
        self,
        telegram_settings,
        agent,
        sessions_storage,
        syncer,
        users_storage,
        resolver,
        bot,
        dispatcher,
    ):
        return FakeTelegramChannel(
            settings=telegram_settings,
            agent=agent,
            sessions_storage=sessions_storage,
            syncer=syncer,
            users_storage=users_storage,
            resolver=resolver,
            bot=bot,
            dispatcher=dispatcher,
        )

    @pytest.mark.asyncio
    async def test_init_creates_bot_and_dispatcher(self, channel, bot, dispatcher):
        assert channel._bot is bot
        assert channel._dispatcher is dispatcher

    @pytest.mark.asyncio
    async def test_get_toolkit_returns_telegram_toolkit(self, channel):
        toolkit = channel.get_toolkit()
        assert isinstance(toolkit, TelegramToolKit)

    @pytest.mark.asyncio
    async def test_start_sets_bot_name_and_commands(self, channel, bot):
        channel.add_task = MagicMock()
        await channel.start()
        bot.set_my_name.assert_awaited()
        bot.set_my_commands.assert_awaited()

    def _make_message(self, chat_id=123, text="hello"):
        message = MagicMock(spec=aiogram.types.Message)
        chat = MagicMock()
        chat.id = chat_id
        message.chat = chat
        from_user = MagicMock()
        from_user.id = 1
        from_user.first_name = "Test"
        from_user.last_name = None
        from_user.username = None
        from_user.language_code = "en"
        message.from_user = from_user
        message.message_id = 1
        message.date = None
        message.text = text
        message.voice = None
        return message

    @pytest.mark.asyncio
    async def test_handle_new_session(self, channel, users_storage):
        from microclaw.users_storages.dto import UserCreate

        message = self._make_message(chat_id=123)
        user = await users_storage.create_user(data=UserCreate())
        channel._get_or_create_user = AsyncMock(return_value=user)
        channel._enqueue_and_process = AsyncMock()
        await channel.handle_new_session(message)

    @pytest.mark.asyncio
    async def test_handle_voice_message_no_stt(self, channel, bot):
        message = self._make_message(chat_id=123)
        message.voice = MagicMock()
        message.voice.file_id = "file_id"
        channel._stt = None
        await channel.handle_voice_message(message)
        bot.send_message.assert_awaited_once_with(
            chat_id=123, text="Voice messages not supported"
        )

    @pytest.mark.asyncio
    async def test_handle_voice_message_success(self, channel, bot):
        message = self._make_message(chat_id=123)
        message.voice = MagicMock()
        message.voice.file_id = "file_id"

        bot.get_file = AsyncMock(return_value=MagicMock(file_path="path"))
        bot.download_file = AsyncMock(
            return_value=MagicMock(read=MagicMock(return_value=b"audio"))
        )
        channel._stt = AsyncMock()
        channel._stt.transcribe_bytes = AsyncMock(
            return_value=AgentMessage(role=AgentMessageRoleEnum.STT, text="transcribed")
        )
        channel._enqueue_and_process = AsyncMock()

        await channel.handle_voice_message(message)
        channel._enqueue_and_process.assert_awaited()

    @pytest.mark.asyncio
    async def test_handle_text_message_reset_button(self, channel):
        message = self._make_message(text=channel.RESET_CONTEXT_BUTTON_TEXT)
        channel.handle_new_session = AsyncMock()
        channel._enqueue_and_process = AsyncMock()
        await channel.handle_text_message(message)
        channel.handle_new_session.assert_awaited()

    @pytest.mark.asyncio
    async def test_handle_text_message_success(self, channel):
        message = self._make_message(text="hello")
        channel._enqueue_and_process = AsyncMock()
        await channel.handle_text_message(message)
        channel._enqueue_and_process.assert_awaited()

    def _make_callback_query(self, chat_id=123):
        callback_query = MagicMock(spec=aiogram.types.CallbackQuery)
        chat = MagicMock()
        chat.id = chat_id
        message = MagicMock()
        message.chat = chat
        message.edit_reply_markup = AsyncMock()
        callback_query.message = message
        callback_query.answer = AsyncMock()
        return callback_query

    @pytest.mark.asyncio
    async def test_handle_confirmation_callback_approve(self, channel, bot):
        callback_query = self._make_callback_query(chat_id=123)
        callback_data = ConfirmationCallbackData(
            session_id=str(uuid.uuid4()), approved="yes"
        )
        channel._process_batch = AsyncMock()
        await channel.handle_confirmation_callback(callback_query, callback_data)
        channel._process_batch.assert_awaited()
        assert callback_query.message.edit_reply_markup.await_count == 1

    @pytest.mark.asyncio
    async def test_handle_confirmation_callback_reject(self, channel, bot):
        callback_query = self._make_callback_query(chat_id=123)
        callback_data = ConfirmationCallbackData(
            session_id=str(uuid.uuid4()), approved="no"
        )
        channel._process_batch = AsyncMock()
        await channel.handle_confirmation_callback(callback_query, callback_data)
        channel._process_batch.assert_awaited()

    @pytest.mark.asyncio
    async def test_get_message_context(self, channel):
        message = self._make_message(chat_id=123)
        message.chat.type = "private"
        message.chat.title = None
        message.chat.username = "testuser"
        message.from_user.last_name = "User"
        message.from_user.username = "test"

        ctx = channel._get_message_context(message)
        assert "123" in ctx
        assert "Test" in ctx

    @pytest.mark.asyncio
    async def test_on_message_queued(self, channel, bot):
        await channel._on_message_queued("123")
        bot.send_message.assert_awaited()

    @pytest.mark.asyncio
    async def test_on_processing_creates_printer(self, channel):
        session_id = uuid.uuid4()
        async with channel._on_processing(
            chat_id=123, session_id=session_id, agent=channel._agent
        ):
            printer = channel._get_printer(123)
            assert printer is not None

    @pytest.mark.asyncio
    async def test_send_system_message(self, channel, bot):
        await channel._send_system_message(123, "hello")
        bot.send_message.assert_awaited()
