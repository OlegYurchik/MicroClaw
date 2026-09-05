import json
import re
import uuid

import aiogram
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from microclaw.agents import Agent
from microclaw.channels.utils import AgentMessageCollector
from microclaw.dto import AgentMessage
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.sessions_storages.filters import SessionFilter


class AgentMessagePrinter(AgentMessageCollector):
    MAX_MESSAGE_LENGTH = 4096
    RESERVED_CHARS = r"_*\[\]()~`>#+-=|{}.!\\"
    RESET_CONTEXT_BUTTON_TEXT = "Reset context"

    def __init__(
        self,
        bot: aiogram.Bot,
        chat_id: int,
        session_id: uuid.UUID,
        sessions_storage: SessionsStorageInterface,
        agent: Agent,
        show_context_usage: bool = False,
        show_costs: bool = False,
        debug: bool = False,
    ):
        super().__init__()
        self._bot = bot
        self._chat_id = chat_id
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
        from .base import ConfirmationCallbackData

        session_id_str = str(self._session_id)
        keyboard = aiogram.types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    aiogram.types.InlineKeyboardButton(
                        text="✅ Confirm",
                        callback_data=ConfirmationCallbackData(
                            session_id=session_id_str, approved="yes"
                        ).pack(),
                    ),
                    aiogram.types.InlineKeyboardButton(
                        text="❌ Cancel",
                        callback_data=ConfirmationCallbackData(
                            session_id=session_id_str, approved="no"
                        ).pack(),
                    ),
                ]
            ]
        )

        description = entry.get("description", "")
        # Inside a code block only ` and \ need escaping
        escaped_description = re.sub(r"([`\\])", r"\\\1", description)

        await self._safe_send(
            text=f"```\n{escaped_description}\n```",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    async def _flush_messages(self):
        for message in self._messages:
            if not message.text:
                continue
            await self.print(text=message.text)
        self._messages = []

    async def print(self, text: str):
        buttons = []
        actual_context_size = 0
        spending = None
        if self._show_context_usage or self._show_costs:
            session = await self._sessions_storage.get_session(
                filter_=SessionFilter(id={self._session_id})
            )
            actual_context_size = session.context_size if session else 0
            spending = session.spending if session else None
        if self._show_context_usage:
            model_context_size = self._agent.get_model_context_window_size()
            if model_context_size:
                context_usage = actual_context_size * 100 / model_context_size
                buttons.append(
                    aiogram.types.InlineKeyboardButton(
                        text=f"{context_usage:.2f}% context",
                        callback_data="null",
                    )
                )
        if self._show_costs and spending is not None:
            buttons.append(
                aiogram.types.InlineKeyboardButton(
                    text=f"{spending.cost:.4f} {spending.currency}",
                    callback_data="null",
                )
            )

        reply_markup = None
        if buttons:
            reply_markup = aiogram.types.InlineKeyboardMarkup(inline_keyboard=[buttons])

        text_list = [
            text[i : i + self.MAX_MESSAGE_LENGTH].strip()
            for i in range(0, len(text), self.MAX_MESSAGE_LENGTH)
        ]

        reset_keyboard = self._get_keyboard()

        for text_chunk in text_list[:-1]:
            if not text_chunk:
                continue
            await self._safe_send(
                text=text_chunk,
                reply_markup=reset_keyboard,
            )
        if text_list and text_list[-1]:
            await self._safe_send(
                text=text_list[-1],
                reply_markup=reply_markup or reset_keyboard,
            )

    async def _safe_send(
        self,
        text: str,
        reply_markup=None,
        parse_mode: ParseMode | None = ParseMode.MARKDOWN_V2,
    ):
        _send = retry(
            retry=retry_if_exception_type(
                (TelegramNetworkError, TelegramRetryAfter, TelegramServerError)
            ),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(self._bot.send_message)

        # Attempt 1: send raw text as MarkdownV2 (LLM is expected to format correctly)
        try:
            await _send(
                chat_id=self._chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return
        except TelegramBadRequest as e:
            error_msg = str(e).lower()
            if "can't parse entities" not in error_msg:
                raise

        # Attempt 2: brute-force escape everything and retry as MarkdownV2
        escaped = self._escape_markdown_v2(text)
        try:
            await _send(
                chat_id=self._chat_id,
                text=escaped,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return
        except TelegramBadRequest as e2:
            if "can't parse entities" not in str(e2).lower():
                raise

        # Attempt 3: plain text without any parse mode
        plain_text = escaped.replace("\\", "")
        await _send(
            chat_id=self._chat_id,
            text=plain_text,
            reply_markup=reply_markup,
            parse_mode=None,
        )

    @staticmethod
    def _escape_markdown_v2(text: str) -> str:
        result = []
        i = 0
        n = len(text)
        reserved = r"_*[]()~`>#+-=|{}.!\\"

        while i < n:
            # Existing escape sequence (already backslashed) — preserve as-is
            if text[i] == "\\" and i + 1 < n and text[i + 1] in reserved:
                result.append(text[i : i + 2])
                i += 2
                continue

            if text[i] in reserved:
                result.append("\\" + text[i])
            else:
                result.append(text[i])
            i += 1

        return "".join(result)

    def _get_keyboard(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=self.RESET_CONTEXT_BUTTON_TEXT)]
            ],
            resize_keyboard=True,
        )
