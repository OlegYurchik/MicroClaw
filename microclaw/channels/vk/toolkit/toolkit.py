from .settings import VKToolKitSettings
from aiohttp import ClientError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from vkbottle.bot import Bot
from vkbottle.exception_factory import VKAPIError

from microclaw.toolkits.base import BaseToolKit, tool


class VKToolKit(BaseToolKit[VKToolKitSettings]):
    """Tools for interacting with VK messages."""

    def __init__(self, key: str, settings, bot: Bot):
        super().__init__(key=key, settings=settings)
        self._bot = bot

    @tool
    async def add_reaction(
        self,
        peer_id: int,
        conversation_message_id: int,
        reaction_id: int,
        message_id: int | None = None,
    ):
        """Add a reaction to a VK message.

        Reaction IDs: 1 👍, 2 ❤️, 3 😂, 4 😮, 5 😢, 6 😡.

        Use the correct message identifier depending on the chat type:
        - Chats (peer_id >= 2000000000): pass the Conversation Message ID
          from the message context as `conversation_message_id`.
        - Private messages (peer_id < 2000000000): pass the Message ID
          from the message context as `message_id`. If `message_id` is
          omitted, `conversation_message_id` is used as a fallback.
        """

        _send_reaction = retry(
            retry=retry_if_exception_type((ClientError, VKAPIError)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(self._bot.api.messages.send_reaction)

        if peer_id >= 2000000000:
            await _send_reaction(
                peer_id=peer_id,
                cmid=conversation_message_id,
                reaction_id=reaction_id,
            )
        else:
            msg_id = message_id if message_id is not None else conversation_message_id
            if msg_id is None:
                raise ValueError(
                    "message_id or conversation_message_id is required for private messages"
                )
            await _send_reaction(
                peer_id=peer_id,
                msg_id=msg_id,
                reaction_id=reaction_id,
            )
