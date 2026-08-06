import json
import random
import uuid

from aiohttp import ClientError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from vkbottle.bot import Bot
from vkbottle.exception_factory import VKAPIError
from vkbottle.tools import Callback, Keyboard, Text
from vkbottle.tools.markdown_parser import markdown

from microclaw.agents import Agent
from microclaw.channels.utils import AgentMessageCollector
from microclaw.dto import AgentMessage
from microclaw.sessions_storages import SessionsStorageInterface


class VKAgentMessagePrinter(AgentMessageCollector):
    MAX_MESSAGE_LENGTH = 4096
    RESET_CONTEXT_BUTTON_TEXT = "Reset context"

    def __init__(
        self,
        bot: Bot,
        peer_id: int,
        session_id: uuid.UUID,
        sessions_storage: SessionsStorageInterface,
        agent: Agent,
        show_context_usage: bool = False,
        show_costs: bool = False,
        debug: bool = False,
    ):
        super().__init__()
        self._bot = bot
        self._peer_id = peer_id
        self._session_id = session_id
        self._sessions_storage = sessions_storage
        self._agent = agent
        self._show_context_usage = show_context_usage
        self._show_costs = show_costs
        self._debug = debug

        self._messages: list[AgentMessage] = []

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        await self._flush_messages()
        if exc_type is not None:
            if self._debug:
                await self.print(text=f"Got exception: {exc_val}")
            else:
                await self.print(
                    text="Internal error, please contact agent administrator",
                )
        await super().__aexit__(exc_type, exc_val, exc_tb)
        return True

    async def handle_new_message(self, new_message: AgentMessage):
        if new_message.role == "request_confirmation":
            entries = json.loads(new_message.text)
            for entry in entries:
                await self._send_confirmation(entry)
            return

        if new_message.role != "assistant" or not new_message.text:
            return

        if self.is_new_message_chunk:
            await self._flush_messages()
            self._messages.append(new_message.model_copy())
        elif new_message.text:
            self._messages[-1].text += new_message.text

    async def _send_confirmation(self, entry: dict):
        keyboard = Keyboard(inline=True)
        keyboard.add(
            Callback(
                "✅ Confirm",
                payload={"session_id": str(self._session_id), "approved": "yes"},
            )
        )
        keyboard.row()
        keyboard.add(
            Callback(
                "❌ Cancel",
                payload={"session_id": str(self._session_id), "approved": "no"},
            )
        )

        description = entry.get("description", "")
        await self._safe_send(
            text=description,
            keyboard=keyboard.get_json(),
        )

    async def _flush_messages(self):
        for message in self._messages:
            if not message.text:
                continue
            await self.print(text=message.text)
        self._messages = []

    def _get_keyboard(self) -> Keyboard:
        keyboard = Keyboard(one_time=False)
        keyboard.add(
            Text(
                f"🔄 {self.RESET_CONTEXT_BUTTON_TEXT}",
                payload={"command": "reset"},
            )
        )
        return keyboard

    async def print(self, text: str):
        text_chunks = [
            text[i : i + self.MAX_MESSAGE_LENGTH].strip()
            for i in range(0, len(text), self.MAX_MESSAGE_LENGTH)
        ]

        keyboard = self._get_keyboard().get_json()

        for chunk in text_chunks[:-1]:
            if not chunk:
                continue
            await self._safe_send(
                text=chunk,
            )

        if text_chunks and text_chunks[-1]:
            await self._safe_send(
                text=text_chunks[-1],
                keyboard=keyboard,
            )

    async def _safe_send(
        self,
        text: str,
        keyboard: str | None = None,
    ) -> None:
        """Send VK message with inline formatting via format_data.

        Parses VK Markdown subset from text and converts to VK format_data.
        Falls back to plain text if API rejects the formatting.
        """
        plain_text, format_data = self._apply_vk_formatting(text)

        _send = retry(
            retry=retry_if_exception_type((ClientError, VKAPIError)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(self._bot.api.messages.send)

        kwargs: dict = {
            "peer_id": self._peer_id,
            "message": plain_text,
            "random_id": random.randint(-2147483648, 2147483647),
        }
        if format_data is not None:
            kwargs["format_data"] = format_data
        if keyboard is not None:
            kwargs["keyboard"] = keyboard

        try:
            await _send(**kwargs)
        except VKAPIError as e:
            error_msg = str(e).lower()
            # Fallback if format_data is rejected
            if "format" in error_msg or "format_data" in error_msg:
                kwargs.pop("format_data", None)
                await _send(**kwargs)
            else:
                raise

    @staticmethod
    def _apply_vk_formatting(text: str) -> tuple[str, str | None]:
        try:
            result = markdown(text)
        except Exception:
            return text, None

        if isinstance(result, str):
            return result, None

        try:
            raw_data = result.as_raw_data()
            if isinstance(raw_data, bytes):
                format_data = raw_data.decode("utf-8")
            else:
                format_data = str(raw_data)
            return str(result), format_data
        except Exception:
            return str(result), None
