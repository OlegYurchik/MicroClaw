import asyncio
from typing import Awaitable, Callable

import aiogram

from microclaw.channels.telegram.utils import TypingManager


class TypingMiddleware(aiogram.BaseMiddleware):
    def __init__(self, delay: float = 3):
        super().__init__()
        self._delay = delay
    
    async def __call__(
            self,
            handler: Callable,
            event: aiogram.types.Message,
            data: dict,
    ) -> Awaitable:
        typing_manager = TypingManager(
            bot=event.bot,
            chat_id=event.chat.id,
            delay=self._delay,
        )
        async with typing_manager:
            return await handler(event, data)
