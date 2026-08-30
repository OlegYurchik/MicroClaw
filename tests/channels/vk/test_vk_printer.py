from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from vkbottle.bot import Bot

from microclaw.channels.vk.printer import VKAgentMessagePrinter
from microclaw.dto import AgentMessage, AgentMessageRoleEnum


class TestVKAgentMessagePrinter:
    @pytest.fixture
    def bot(self):
        bot = MagicMock(spec=Bot)
        bot.api = MagicMock()
        bot.api.messages = MagicMock()
        bot.api.messages.send = AsyncMock()
        return bot

    @pytest.fixture
    def printer(self, bot, sessions_storage, agent):
        return VKAgentMessagePrinter(
            bot=bot,
            peer_id=123,
            session_id=uuid.uuid4(),
            sessions_storage=sessions_storage,
            agent=agent,
        )

    @pytest.mark.asyncio
    async def test_handle_new_message_confirmation(self, printer, bot):
        msg = AgentMessage(
            role=AgentMessageRoleEnum.REQUEST_CONFIRMATION,
            text='[{"description": "test action"}]',
        )
        await printer.handle_new_message(msg)
        bot.api.messages.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_handle_new_message_assistant(self, printer):
        msg = AgentMessage(role=AgentMessageRoleEnum.ASSISTANT, text="hello")
        await printer.handle_new_message(msg)
        assert len(printer._messages) == 1
        assert printer._messages[0].text == "hello"

    @pytest.mark.asyncio
    async def test_flush_messages(self, printer, bot):
        msg = AgentMessage(role=AgentMessageRoleEnum.ASSISTANT, text="hello")
        printer._messages.append(msg)
        await printer._flush_messages()
        bot.api.messages.send.assert_awaited()
        assert printer._messages == []

    @pytest.mark.asyncio
    async def test_print_splits_long_text(self, printer, bot):
        long_text = "a" * 5000
        await printer.print(text=long_text)
        assert bot.api.messages.send.await_count >= 2

    @pytest.mark.asyncio
    async def test_print_with_context_usage(self, bot, sessions_storage, agent):
        printer = VKAgentMessagePrinter(
            bot=bot,
            peer_id=123,
            session_id=uuid.uuid4(),
            sessions_storage=sessions_storage,
            agent=agent,
            show_context_usage=True,
        )
        await printer.print(text="hello")
        bot.api.messages.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_print_with_costs(self, bot, sessions_storage, agent):
        printer = VKAgentMessagePrinter(
            bot=bot,
            peer_id=123,
            session_id=uuid.uuid4(),
            sessions_storage=sessions_storage,
            agent=agent,
            show_costs=True,
        )
        await printer.print(text="hello")
        bot.api.messages.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_safe_send(self, printer, bot):
        await printer._safe_send(text="hello")
        bot.api.messages.send.assert_awaited()
        assert bot.api.messages.send.await_args.kwargs["peer_id"] == 123

    @pytest.mark.asyncio
    async def test_aexit(self, bot, sessions_storage, agent):
        printer = VKAgentMessagePrinter(
            bot=bot,
            peer_id=123,
            session_id=uuid.uuid4(),
            sessions_storage=sessions_storage,
            agent=agent,
            debug=False,
        )
        async with printer:
            raise ValueError("test error")
        assert "Internal error" in bot.api.messages.send.await_args.kwargs["message"]
