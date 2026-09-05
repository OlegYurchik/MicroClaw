import contextlib
import contextvars
import socket
import uuid

from .middlewares.auth import AuthMiddleware
from .middlewares.typing import TypingMiddleware
from .printer import AgentMessagePrinter
from .settings import TelegramIPFamilyEnum, TelegramSettings
from .toolkit import TelegramToolKit
import aiogram
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.filters.callback_data import CallbackData
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from microclaw.agents import Agent
from microclaw.channels.base import BaseChannel
from microclaw.dto import AgentMessage, DecisionEnum
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.stt import STT
from microclaw.syncers import SyncerInterface
from microclaw.toolkits import ToolKitSettings
from microclaw.users_storages import UsersStorageInterface
from microclaw.utils import suppress_exception
from microclaw.utils.context import (
    set_current_request_id,
)


class ConfirmationCallbackData(CallbackData, prefix="confirm"):
    session_id: str
    approved: str


class BaseTelegramChannel(BaseChannel):
    r"""Format all responses as Telegram MarkdownV2.

    YOU are responsible for correct escaping. Escape these 18 chars with \ in normal text:
    _ * [ ] ( ) ~ ` > # + - = | { } . !

    Exceptions:
    - Inside `inline code` / ```code blocks```: escape ONLY ` and \
    - Inside link URLs (parentheses): escape ONLY ) and \

    Allowed: *bold*, _italic_, __underline__, ~strikethrough~, ||spoiler||, `code`, ```block```, [label](URL), >quote, **>expandable quote.
    Nesting allowed except inside code. Use \r between _italic_ and __underline__ if adjacent.
    Prohibited: headers, lists, rules, tables, HTML.

    If your escaping is wrong, the message may be sent as plain text instead.
    """
    END_PHRASE = "NO_REPLY"
    TYPING_ACTION_DELAY = 3
    MAX_MESSAGE_LENGTH = 4096
    CHAT_ID_CONTEXT = contextvars.ContextVar("chat_id", default=None)
    RESET_CONTEXT_BUTTON_TEXT = "Reset context"
    QUEUED_MESSAGE_TEXT = "⏳ Message queued"

    def _get_keyboard(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=self.RESET_CONTEXT_BUTTON_TEXT)]
            ],
            resize_keyboard=True,
        )

    def __init__(
        self,
        settings: TelegramSettings,
        agent: Agent,
        sessions_storage: SessionsStorageInterface,
        syncer: SyncerInterface,
        users_storage: UsersStorageInterface,
        resolver: "DependencyResolver",  # noqa: F821
        stt: STT | None = None,
        channel_key: str = "default",
    ):
        super().__init__(
            settings=settings,
            agent=agent,
            sessions_storage=sessions_storage,
            stt=stt,
            channel_key=channel_key,
            syncer=syncer,
            users_storage=users_storage,
            resolver=resolver,
        )

        session = None
        if settings.ip_family != TelegramIPFamilyEnum.AUTO:
            family = (
                socket.AF_INET
                if settings.ip_family == TelegramIPFamilyEnum.IPV4
                else socket.AF_INET6
            )
            session = AiohttpSession()
            session._connector_init.update(
                family=family,
                ttl_dns_cache=300,
            )
        self._bot = aiogram.Bot(token=settings.token, session=session)
        self._dispatcher = aiogram.Dispatcher()
        self._printers: dict[int, AgentMessagePrinter] = {}
        self._dispatcher.message.middleware(
            AuthMiddleware(allow_from=self._settings.allow_from)
        )
        self._dispatcher.message.middleware(
            TypingMiddleware(delay=self.TYPING_ACTION_DELAY)
        )
        self._dispatcher.message(aiogram.filters.Command("reset"))(
            self.handle_new_session
        )
        self._dispatcher.message(aiogram.filters.Command("start"))(
            self.handle_new_session
        )
        self._dispatcher.message(aiogram.F.voice)(self.handle_voice_message)
        self._dispatcher.message()(self.handle_text_message)
        self._dispatcher.callback_query(ConfirmationCallbackData.filter())(
            self.handle_confirmation_callback
        )

    def get_toolkit(self) -> TelegramToolKit:
        toolkit_settings = ToolKitSettings(
            path="microclaw.channels.telegram.toolkit.TelegramToolKit",
            args={"bot_token": self._settings.token},
        )
        return TelegramToolKit(key="telegram_channel", settings=toolkit_settings)

    @classmethod
    def get_current_chat_id(cls) -> int | None:
        return cls.CHAT_ID_CONTEXT.get(None)

    @contextlib.contextmanager
    def set_current_chat_id(self, chat_id: int):
        chat_id_token = self.CHAT_ID_CONTEXT.set(chat_id)
        try:
            yield
        finally:
            self.CHAT_ID_CONTEXT.reset(chat_id_token)

    async def start(self):
        set_bot_name_function = suppress_exception()(self._bot.set_my_name)
        await set_bot_name_function(name=self._settings.name)

        commands = [
            aiogram.types.BotCommand(
                command="reset",
                description="Dialog context reset",
            ),
        ]
        set_bot_commands_function = suppress_exception()(self._bot.set_my_commands)
        await set_bot_commands_function(commands)

        self.add_task(self.listen_events())

    async def listen_events(self):
        raise NotImplementedError

    async def handle_new_session(self, message: aiogram.types.Message):
        await super().handle_new_session(message.chat.id)

    async def handle_voice_message(self, message: aiogram.types.Message):
        chat_id = message.chat.id
        request_id = uuid.uuid4()
        logger.info(
            f"[{request_id}] Received voice message event chat_id={chat_id}",
        )
        with set_current_request_id(request_id):
            user = await self._get_or_create_user(chat_id)
            agent = await self.get_agent_for_user(user) or self._agent

            if self._stt is None:
                await self._bot.send_message(
                    chat_id=chat_id,
                    text="Voice messages not supported",
                )
                return

            _get_file = retry(
                retry=retry_if_exception_type(
                    (TelegramNetworkError, TelegramRetryAfter, TelegramServerError)
                ),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
            )(self._bot.get_file)
            _download_file = retry(
                retry=retry_if_exception_type(
                    (TelegramNetworkError, TelegramRetryAfter, TelegramServerError)
                ),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
            )(self._bot.download_file)

            file = await _get_file(message.voice.file_id)
            audio_bytes_io = await _download_file(file.file_path)
            audio_bytes = audio_bytes_io.read()
            audio_format = "ogg"

            stt_message = await self._stt.transcribe_bytes(
                audio_bytes, format=audio_format
            )

            context_info = self._get_message_context(message=message)
            text_with_context = f"""
            {context_info}
            IMPORTANT: It is voice message

            ##User message:
            {stt_message.text}
            """

            new_messages = [
                AgentMessage(role="user", audio=audio_bytes, audio_format=audio_format),
                stt_message,
                AgentMessage(role="stt", text=text_with_context),
            ]
            logger.info(
                f"[{request_id}] Starting processing for chat_id={chat_id}",
            )
            await self._enqueue_and_process(
                chat_id=chat_id,
                new_messages=new_messages,
                agent=agent,
            )
            logger.info(
                f"[{request_id}] Finished processing for chat_id={chat_id}",
            )

    async def handle_text_message(self, message: aiogram.types.Message):
        chat_id = message.chat.id
        request_id = uuid.uuid4()
        logger.info(
            f"[{request_id}] Received text message event chat_id={chat_id}",
        )
        with set_current_request_id(request_id):
            user = await self._get_or_create_user(chat_id)
            agent = await self.get_agent_for_user(user) or self._agent

            text = (message.text or "").strip()
            if text == self.RESET_CONTEXT_BUTTON_TEXT:
                await self.handle_new_session(message)
                return

            context_info = self._get_message_context(message=message)
            text_with_context = f"""
            {context_info}

            ##User message:
            {text}
            """

            new_messages = [AgentMessage(role="user", text=text_with_context)]
            logger.info(
                f"[{request_id}] Starting processing for chat_id={chat_id}",
            )
            await self._enqueue_and_process(
                chat_id=chat_id,
                new_messages=new_messages,
                agent=agent,
            )
            logger.info(
                f"[{request_id}] Finished processing for chat_id={chat_id}",
            )

    async def handle_confirmation_callback(
        self,
        callback_query: aiogram.types.CallbackQuery,
        callback_data: ConfirmationCallbackData,
    ):
        request_id = uuid.uuid4()
        logger.info(
            f"[{request_id}] Received confirmation callback event chat_id={callback_query.message.chat.id}",
        )
        with set_current_request_id(request_id):
            chat_id = callback_query.message.chat.id
            approved = callback_data.approved == "yes"
            session_id = uuid.UUID(callback_data.session_id)
            user = await self._get_or_create_user(chat_id)
            agent = await self.get_agent_for_user(user) or self._agent

            async with self._lock_chat_for_processing(chat_id):
                status_text = "✅ Confirmed" if approved else "❌ Rejected"
                keyboard = aiogram.types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            aiogram.types.InlineKeyboardButton(
                                text=status_text,
                                callback_data="null",
                            ),
                        ],
                    ],
                )
                _edit_reply_markup = retry(
                    retry=retry_if_exception_type(
                        (TelegramNetworkError, TelegramRetryAfter, TelegramServerError)
                    ),
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=1, max=10),
                    reraise=True,
                )(callback_query.message.edit_reply_markup)
                _answer = retry(
                    retry=retry_if_exception_type(
                        (TelegramNetworkError, TelegramRetryAfter, TelegramServerError)
                    ),
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=1, max=10),
                    reraise=True,
                )(callback_query.answer)

                await _edit_reply_markup(reply_markup=keyboard)
                await _answer()

                decision = DecisionEnum.APPROVE if approved else DecisionEnum.REJECT
                await self._process_batch(
                    chat_id=chat_id,
                    session_id=session_id,
                    agent=agent,
                    batch=[],
                    decision=decision,
                )

    def _get_message_context(self, message: aiogram.types.Message) -> str:
        chat_title = getattr(message.chat, "title", None)
        chat_username = getattr(message.chat, "username", None)

        return f"""
        ## Chat Info
        ID: {message.chat.id}
        Type: {message.chat.type}
        {f"Title: {chat_title}" if chat_title else ""}
        {f"Username: {chat_username}" if chat_username else ""}

        ## User Info
        ID: {message.from_user.id}
        First Name: {message.from_user.first_name}
        Last Name: {message.from_user.last_name}
        Username: {message.from_user.username}
        Language: {message.from_user.language_code}

        ## Message Info
        ID: {message.message_id}
        Date: {message.date.isoformat() if message.date else None}
        """

    async def _on_message_queued(self, chat_id: str | int) -> None:
        try:
            await self._bot.send_message(
                chat_id=int(chat_id),
                text=self.QUEUED_MESSAGE_TEXT,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception:
            logger.opt(exception=True).warning("Failed to send queued notification")

    def _get_printer(self, chat_id: str | int) -> AgentMessagePrinter | None:
        return self._printers.get(str(chat_id))

    async def _on_agent_message(
        self,
        chat_id: str | int,
        session_id: uuid.UUID,
        agent: Agent,
        msg: AgentMessage,
    ) -> None:
        printer = self._get_printer(chat_id)
        if printer is not None:
            await printer.register_new_message(msg)

    async def _on_confirmation_request(
        self,
        chat_id: str | int,
        session_id: uuid.UUID,
        agent: Agent,
        entries: list[dict],
    ) -> None:
        printer = self._get_printer(chat_id)
        if printer is not None:
            for entry in entries:
                await printer._send_confirmation(entry)

    def _get_printer(self, chat_id: str | int) -> AgentMessagePrinter | None:
        return self._printers.get(str(chat_id))

    async def _on_agent_message(
        self,
        chat_id: str | int,
        session_id: uuid.UUID,
        agent: Agent,
        msg: AgentMessage,
    ) -> None:
        printer = self._get_printer(chat_id)
        if printer is not None:
            await printer.register_new_message(msg)

    async def _on_confirmation_request(
        self,
        chat_id: str | int,
        session_id: uuid.UUID,
        agent: Agent,
        entries: list[dict],
    ) -> None:
        printer = self._get_printer(chat_id)
        if printer is not None:
            for entry in entries:
                await printer._send_confirmation(entry)

    @contextlib.asynccontextmanager
    async def _on_processing(
        self,
        chat_id: str | int,
        session_id: uuid.UUID,
        agent: Agent,
    ):
        cid = str(chat_id)
        printer = AgentMessagePrinter(
            bot=self._bot,
            chat_id=int(chat_id),
            session_id=session_id,
            sessions_storage=self._sessions_storage,
            agent=agent,
            show_context_usage=self._settings.show_context_usage,
            show_costs=self._settings.show_costs,
            debug=self._settings.debug,
        )
        self._printers[cid] = printer
        async with printer:
            try:
                yield
            finally:
                self._printers.pop(cid, None)

    async def _send_system_message(self, chat_id: str | int, text: str | None) -> None:
        if text is None:
            return
        text = text[:self.MAX_MESSAGE_LENGTH]

        _send = retry(
            retry=retry_if_exception_type(
                (TelegramNetworkError, TelegramRetryAfter, TelegramServerError)
            ),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(self._bot.send_message)

        escaped_text = AgentMessagePrinter._escape_markdown_v2(text)
        await _send(
            chat_id=int(chat_id),
            text=escaped_text,
            reply_markup=self._get_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
