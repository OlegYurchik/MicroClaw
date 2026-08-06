import asyncio

from aiogram.exceptions import (
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from microclaw.channels.telegram.base import BaseTelegramChannel


class TelegramPollingChannel(BaseTelegramChannel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._polling_task = None
        self._stop_event = asyncio.Event()

    async def listen_events(self):
        _delete_webhook = retry(
            retry=retry_if_exception_type(
                (TelegramNetworkError, TelegramRetryAfter, TelegramServerError)
            ),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(self._bot.delete_webhook)

        await _delete_webhook()
        self.add_task(
            self._dispatcher.start_polling(self._bot, handle_signals=False),
        )
