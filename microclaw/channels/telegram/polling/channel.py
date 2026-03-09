import asyncio

from microclaw.channels.telegram.base import BaseTelegramChannel


class TelegramPollingChannel(BaseTelegramChannel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._polling_task = None
        self._stop_event = asyncio.Event()

    async def listen_events(self):
        await self._bot.delete_webhook()
        self.add_task(
            self._dispatcher.start_polling(self._bot, handle_signals=False),
        )
