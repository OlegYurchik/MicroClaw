from vkbottle.bot import Bot

from microclaw.toolkits.base import BaseToolKit, tool
from .settings import VKToolKitSettings


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
    ):
        """Add a reaction to a VK message.

        Common VK reaction IDs:
        1 - 👍 (thumbs up)
        2 - ❤️ (heart)
        3 - 😂 (laugh)
        4 - 😮 (wow)
        5 - 😢 (sad)
        6 - 😡 (angry)

        Args:
            peer_id: The ID of the peer where the message is located
            conversation_message_id: The conversation message ID to react to
            reaction_id: The reaction ID to add (e.g. 1, 2, 3, 4, 5, 6)
        """
        await self._bot.api.messages.send_reaction(
            peer_id=peer_id,
            cmid=conversation_message_id,
            reaction_id=reaction_id,
        )
