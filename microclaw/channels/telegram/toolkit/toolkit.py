from .settings import TelegramToolKitSettings
import aiogram
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

from microclaw.toolkits.base import BaseToolKit, tool


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
        bot = aiogram.Bot(token=self.arguments.bot_token)

        _set_reaction = retry(
            retry=retry_if_exception_type(
                (TelegramNetworkError, TelegramRetryAfter, TelegramServerError)
            ),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(bot.set_message_reaction)

        await _set_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[aiogram.types.ReactionTypeEmoji(emoji=emoji)],
        )
        await bot.session.close()
