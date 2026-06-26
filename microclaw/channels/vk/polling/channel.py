import logging

from microclaw.channels.vk.base import BaseVKChannel

logger = logging.getLogger(__name__)


class VKPollingChannel(BaseVKChannel):
    async def listen_events(self):
        logger.info("VK polling started for group")
        await self._bot.run_polling()
