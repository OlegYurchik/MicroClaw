import aiogram

from microclaw.toolkits.base import BaseToolKit, tool
from .settings import TelegramToolKitSettings


class TelegramToolKit(BaseToolKit[TelegramToolKitSettings]):
    """Tools for interacting with Telegram messages."""

    @tool
    async def add_reaction(
            self,
            chat_id: int,
            message_id: int,
            emoji: str,
    ):
        """Add a reaction emoji to a Telegram message.

        Use this tool when you want to show that a user's message has evoked an emotion in you
        and you want to set an appropriate reaction.

        Args:
            chat_id: The ID of the chat where the message is located
            message_id: The ID of the message to react to
            emoji: The emoji reaction to add (e.g., "👍", "❤️", "🎉")
        """
        bot = aiogram.Bot(token=self.settings.bot_token)

        await bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[aiogram.types.ReactionTypeEmoji(emoji=emoji)],
        )
        await bot.session.close()
