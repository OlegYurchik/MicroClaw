import asyncio
from typing import Awaitable, Callable

import aiogram


class TypingMiddleware(aiogram.BaseMiddleware):
    def __init__(self, delay: float = 3):
        super().__init__()
        self.delay = delay
    
    async def __call__(
            self,
            handler: Callable,
            event: aiogram.types.Message,
            data: dict,
    ) -> Awaitable:
        async def send_typing():
            while True:
                try:
                    await event.bot.send_chat_action(
                        chat_id=event.chat.id,
                        action="typing",
                    )
                except Exception:
                    break
                await asyncio.sleep(self.delay)
        
        typing_task = asyncio.create_task(send_typing())
        try:
            return await handler(event, data)
        finally:
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass
