import asyncio
from unittest.mock import AsyncMock

import aiogram
import pytest

from microclaw.channels.telegram.utils import TypingManager


class TestTypingManager:
    @pytest.fixture
    def bot(self):
        return AsyncMock(spec=aiogram.Bot)

    @pytest.mark.asyncio
    async def test_typing_manager_start_stop(self, bot):
        manager = TypingManager(bot=bot, chat_id=123, delay=0.1)
        await manager.start_task()
        assert manager._background_task is not None
        await manager.stop_task()
        assert manager._background_task is None

    @pytest.mark.asyncio
    async def test_typing_manager_context_manager(self, bot):
        manager = TypingManager(bot=bot, chat_id=123, delay=0.1)
        async with manager:
            assert manager._background_task is not None
        assert manager._background_task is None

    @pytest.mark.asyncio
    async def test_typing_manager_run_sends_action(self, bot):
        manager = TypingManager(bot=bot, chat_id=123, delay=0.05)
        await manager.start_task()
        await asyncio.sleep(0.08)
        await manager.stop_task()
        bot.send_chat_action.assert_awaited()
        assert bot.send_chat_action.await_args.kwargs["chat_id"] == 123
        assert bot.send_chat_action.await_args.kwargs["action"] == "typing"

    @pytest.mark.asyncio
    async def test_typing_manager_run_ignores_errors(self, bot):
        bot.send_chat_action.side_effect = RuntimeError("boom")
        manager = TypingManager(bot=bot, chat_id=123, delay=0.05)
        await manager.start_task()
        await asyncio.sleep(0.08)
        await manager.stop_task()
        # should not raise

    @pytest.mark.asyncio
    async def test_typing_manager_cancel(self, bot):
        manager = TypingManager(bot=bot, chat_id=123, delay=0.1)
        await manager.start_task()
        await manager.stop_task()
        assert manager._background_task is None
