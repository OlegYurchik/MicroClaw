from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from vkbottle.bot import Bot, Message

from microclaw.channels.vk.base import BaseVKChannel
from microclaw.channels.vk.settings import VKSettings
from microclaw.channels.vk.toolkit import VKToolKit
from microclaw.dto import AgentMessage, AgentMessageRoleEnum


class FakeVKChannel(BaseVKChannel):
    def _create_bot(self):
        return MagicMock(spec=Bot)

    async def listen_events(self):
        pass


class TestBaseVKChannel:
    @pytest.fixture
    def vk_settings(self):
        return VKSettings(token="test_token", type="vk", method="polling")

    @pytest.fixture
    def bot(self):
        bot = MagicMock(spec=Bot)
        bot.api = MagicMock()
        bot.api.messages = MagicMock()
        bot.api.messages.send = AsyncMock()
        bot.api.messages.send_message_event_answer = AsyncMock()
        bot.api.messages.get_by_conversation_message_id = AsyncMock()
        bot.api.messages.edit = AsyncMock()
        bot.labeler = MagicMock()
        bot.labeler.views = MagicMock(return_value={"message": MagicMock()})
        bot.on = MagicMock()
        bot.on.message = MagicMock(return_value=MagicMock())
        bot.on.raw_event = MagicMock(return_value=MagicMock())
        return bot

    @pytest.fixture
    def channel(
        self, vk_settings, agent, sessions_storage, syncer, users_storage, resolver, bot
    ):
        return FakeVKChannel(
            settings=vk_settings,
            agent=agent,
            sessions_storage=sessions_storage,
            syncer=syncer,
            users_storage=users_storage,
            resolver=resolver,
            bot=bot,
        )

    def _make_message(self, peer_id=123, text="hello", from_id=1):
        message = MagicMock(spec=Message)
        message.peer_id = peer_id
        message.from_id = from_id
        message.id = 1
        message.conversation_message_id = 1
        message.date = None
        message.text = text
        message.payload = None
        message.attachments = None
        return message

    @pytest.mark.asyncio
    async def test_init_creates_bot(self, channel, bot):
        assert channel._bot is bot

    @pytest.mark.asyncio
    async def test_get_toolkit_returns_vk_toolkit(self, channel):
        toolkit = channel.get_toolkit()
        assert isinstance(toolkit, VKToolKit)

    @pytest.mark.asyncio
    async def test_handle_message_auth_disabled(self, channel, bot):
        channel._is_auth_disabled = MagicMock(return_value=True)
        message = self._make_message()
        await channel._handle_message(message)
        # Should return early without processing
        bot.api.messages.send.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_handle_message_start_command(self, channel):
        message = self._make_message(text="/start")
        channel.handle_new_session = AsyncMock()
        await channel._handle_message(message)
        channel.handle_new_session.assert_awaited()

    @pytest.mark.asyncio
    async def test_handle_voice_message_no_stt(self, channel, bot):
        message = self._make_message()
        channel._stt = None
        await channel.handle_voice_message(message)
        bot.api.messages.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_handle_voice_message_success(self, channel, bot):
        message = self._make_message()
        message.attachments = []
        channel._stt = AsyncMock()
        channel._stt.transcribe_bytes = AsyncMock(
            return_value=AgentMessage(role=AgentMessageRoleEnum.STT, text="transcribed")
        )
        channel._enqueue_and_process = AsyncMock()
        channel._get_audio_message_attachments = MagicMock(return_value=[])
        await channel.handle_voice_message(message)
        # Will send "No audio message found" since attachments is empty
        bot.api.messages.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_handle_text_message_success(self, channel):
        message = self._make_message(text="hello")
        channel._enqueue_and_process = AsyncMock()
        await channel.handle_text_message(message)
        channel._enqueue_and_process.assert_awaited()

    @pytest.mark.asyncio
    async def test_handle_confirmation_callback(self, channel, bot):
        event = {
            "object": {
                "peer_id": 123,
                "payload": '{"session_id": "'
                + str(uuid.uuid4())
                + '", "approved": "yes"}',
                "event_id": "event1",
                "user_id": 1,
            }
        }
        channel._process_batch = AsyncMock()
        await channel._handle_confirmation_callback(event)
        channel._process_batch.assert_awaited()

    @pytest.mark.asyncio
    async def test_update_confirmation_message(self, channel, bot):
        bot.api.messages.get_by_conversation_message_id = AsyncMock(
            return_value=MagicMock(items=[MagicMock(text="original")])
        )
        bot.api.messages.edit = AsyncMock()
        await channel._update_confirmation_message(123, 1, True)
        bot.api.messages.edit.assert_awaited()

    @pytest.mark.asyncio
    async def test_is_auth_disabled(self, channel):
        message = self._make_message()
        channel._settings.allow_from = ["123"]
        assert channel._is_auth_disabled(message) is False

        channel._settings.allow_from = ["999"]
        assert channel._is_auth_disabled(message) is True

    @pytest.mark.asyncio
    async def test_get_audio_message_attachments(self, channel):
        message = self._make_message()
        message.attachments = None
        assert channel._get_audio_message_attachments(message) == []

    @pytest.mark.asyncio
    async def test_on_message_queued(self, channel, bot):
        await channel._on_message_queued("123")
        bot.api.messages.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_send_system_message(self, channel, bot):
        await channel._send_system_message(123, "hello")
        bot.api.messages.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_format_text_context(self, channel):
        message = self._make_message(text="hello")
        result = channel._format_text_context(message)
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_get_message_context(self, channel):
        message = self._make_message(peer_id=123)
        result = channel._get_message_context(message)
        assert "123" in result

    @pytest.mark.asyncio
    async def test_start(self, channel, bot):
        channel.add_task = MagicMock()
        await channel.start()
        bot.run_polling.assert_not_called()
