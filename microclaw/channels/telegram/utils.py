import asyncio


class TypingManager:
    def __init__(self, bot: aiogram.Bot, chat_id: int, delay: int = 3):
        self._bot = bot
        self._chat_id = chat_id
        self._delay = delay
        self._background_task = None

    async def __aenter__(self):
        await self.stop_task()
        await self.start_task()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop_task()

    async def start_task(self):
        if self._background_task is None:
            self._background_task = asyncio.create_task(self.run())

    async def stop_task(self):
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass

    async def run(self):
        while True:
            try:
                await self._bot.send_chat_action(
                    chat_id=self._chat_id,
                    action="typing",
                )
            except Exception:
                pass
            finally:
                await asyncio.sleep(self._delay)
