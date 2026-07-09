from typing import Any

from vkbottle.bot import Message
from vkbottle.dispatch.middlewares.abc import BaseMiddleware
from loguru import logger


class VKTypingMiddleware(BaseMiddleware[Message]):
    async def pre(self) -> None:
        try:
            await self.event.ctx_api.messages.set_activity(
                peer_id=self.event.peer_id,
                type="typing",
            )
        except Exception:
            logger.debug("Failed to send VK typing activity")

    async def post(self) -> None:
        pass
