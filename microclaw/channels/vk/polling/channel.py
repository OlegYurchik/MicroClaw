from loguru import logger
from vkbottle.bot import Bot
from vkbottle.polling import BotPolling

from microclaw.channels.vk.base import BaseVKChannel


class VKPollingChannel(BaseVKChannel):
    def _create_bot(self) -> Bot:
        return Bot(token=self._settings.token, polling=BotPolling())

    async def listen_events(self):
        logger.info("VK polling started for group")
        await self._bot.run_polling()
