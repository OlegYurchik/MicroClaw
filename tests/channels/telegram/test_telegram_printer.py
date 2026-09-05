from unittest.mock import AsyncMock
import uuid

import aiogram
from aiogram.enums import ParseMode
import pytest

from microclaw.channels.telegram.printer import AgentMessagePrinter
from microclaw.dto import AgentMessage, AgentMessageRoleEnum


class TestAgentMessagePrinter:
    @pytest.fixture
    def bot(self):
        return AsyncMock(spec=aiogram.Bot)

    @pytest.fixture
    def printer(self, bot, sessions_storage, agent):
        return AgentMessagePrinter(
            bot=bot,
            chat_id=123,
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
        bot.send_message.assert_awaited()
        reply_markup = bot.send_message.await_args.kwargs.get("reply_markup")
        assert reply_markup is not None

    @pytest.mark.asyncio
    async def test_handle_new_message_assistant_text(self, printer):
        msg = AgentMessage(role=AgentMessageRoleEnum.ASSISTANT, text="hello")
        await printer.handle_new_message(msg)
        assert len(printer._messages) == 1
        assert printer._messages[0].text == "hello"

    @pytest.mark.asyncio
    async def test_handle_new_message_chunk(self, printer):
        msg1 = AgentMessage(
            role=AgentMessageRoleEnum.ASSISTANT, text="hello", chunked_message_id="1"
        )
        msg2 = AgentMessage(
            role=AgentMessageRoleEnum.ASSISTANT, text=" world", chunked_message_id="1"
        )
        await printer.register_new_message(msg1)
        await printer.register_new_message(msg2)
        # Same chunked_message_id should append text, not create new message
        assert len(printer._messages) == 1
        assert printer._messages[0].text == "hello world"

    @pytest.mark.asyncio
    async def test_flush_messages(self, printer, bot):
        msg = AgentMessage(role=AgentMessageRoleEnum.ASSISTANT, text="hello")
        printer._messages.append(msg)
        await printer._flush_messages()
        bot.send_message.assert_awaited()
        assert printer._messages == []

    @pytest.mark.asyncio
    async def test_print_splits_long_text(self, printer, bot):
        long_text = "a" * 5000
        await printer.print(text=long_text)
        assert bot.send_message.await_count >= 2

    @pytest.mark.asyncio
    async def test_print_context_usage_button(self, bot, sessions_storage, agent):
        printer = AgentMessagePrinter(
            bot=bot,
            chat_id=123,
            session_id=uuid.uuid4(),
            sessions_storage=sessions_storage,
            agent=agent,
            show_context_usage=True,
        )
        await printer.print(text="hello")
        reply_markup = bot.send_message.await_args.kwargs.get("reply_markup")
        assert reply_markup is not None

    @pytest.mark.asyncio
    async def test_print_costs_button(self, bot, sessions_storage, agent):
        printer = AgentMessagePrinter(
            bot=bot,
            chat_id=123,
            session_id=uuid.uuid4(),
            sessions_storage=sessions_storage,
            agent=agent,
            show_costs=True,
        )
        await printer.print(text="hello")
        reply_markup = bot.send_message.await_args.kwargs.get("reply_markup")
        assert reply_markup is not None

    @pytest.mark.asyncio
    async def test_safe_send_markdown_v2(self, printer, bot):
        await printer._safe_send(text="hello")
        bot.send_message.assert_awaited()
        assert bot.send_message.await_args.kwargs["parse_mode"] == ParseMode.MARKDOWN_V2

    @pytest.mark.asyncio
    async def test_safe_send_plain_fallback(self, printer, bot):
        from aiogram.exceptions import TelegramBadRequest
        from aiogram.methods import SendMessage

        bot.send_message.side_effect = [
            TelegramBadRequest(
                method=SendMessage(chat_id=1, text=""), message="can't parse entities"
            ),
            TelegramBadRequest(
                method=SendMessage(chat_id=1, text=""), message="can't parse entities"
            ),
            None,
        ]
        await printer._safe_send(text="hello")
        assert bot.send_message.await_count == 3

    @pytest.mark.asyncio
    async def test_aexit_debug(self, bot, sessions_storage, agent):
        printer = AgentMessagePrinter(
            bot=bot,
            chat_id=123,
            session_id=uuid.uuid4(),
            sessions_storage=sessions_storage,
            agent=agent,
            debug=True,
        )
        async with printer:
            raise ValueError("test error")
        assert "Got exception" in bot.send_message.await_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_aexit_no_debug(self, bot, sessions_storage, agent):
        printer = AgentMessagePrinter(
            bot=bot,
            chat_id=123,
            session_id=uuid.uuid4(),
            sessions_storage=sessions_storage,
            agent=agent,
            debug=False,
        )
        async with printer:
            raise ValueError("test error")
        assert "Internal error" in bot.send_message.await_args.kwargs["text"]
