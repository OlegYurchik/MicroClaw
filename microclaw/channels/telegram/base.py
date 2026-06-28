import asyncio
import contextlib
import socket
import uuid

import aiogram
import contextvars
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters.callback_data import CallbackData
from loguru import logger

from microclaw.agents import Agent
from microclaw.channels.base import BaseChannel
from microclaw.channels.settings import ChannelTypeEnum
from microclaw.channels.utils import AgentMessageSaver
from microclaw.dto import AgentMessage
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.sessions_storages.filters import MessageFilter
from microclaw.stt import STT
from microclaw.syncers import SyncerInterface
from microclaw.users_storages import UsersStorageInterface
from microclaw.toolkits import ToolKitSettings
from microclaw.utils import suppress_exception
from .middlewares.auth import AuthMiddleware
from .middlewares.typing import TypingMiddleware
from .printer import AgentMessagePrinter
from .settings import TelegramIPFamilyEnum, TelegramSettings
from .toolkit import TelegramToolKit


class ConfirmationCallbackData(CallbackData, prefix="confirm"):
    id: str
    approved: str


class BaseTelegramChannel(BaseChannel):
    END_PHRASE = "NO_REPLY"
    TYPING_ACTION_DELAY = 3
    MAX_MESSAGE_LENGTH = 4096
    CHAT_ID_CONTEXT = contextvars.ContextVar("chat_id", default=None)

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
            family = socket.AF_INET if settings.ip_family == TelegramIPFamilyEnum.IPV4 else socket.AF_INET6
            session = AiohttpSession()
            session._connector_init.update(
                family=family,
                ttl_dns_cache=300,
            )
        self._bot = aiogram.Bot(token=settings.token, session=session)
        self._dispatcher = aiogram.Dispatcher()
        self._dispatcher.message.middleware(AuthMiddleware(allow_from=self._settings.allow_from))
        self._dispatcher.message.middleware(TypingMiddleware(delay=self.TYPING_ACTION_DELAY))
        self._dispatcher.message(aiogram.filters.Command("reset"))(self.handle_new_session)
        self._dispatcher.message(aiogram.filters.Command("start"))(self.handle_new_session)
        self._dispatcher.message(aiogram.F.voice)(self.handle_voice_message)
        self._dispatcher.message()(self.handle_text_message)
        self._dispatcher.callback_query(ConfirmationCallbackData.filter())(self.handle_confirmation_callback)

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

    async def start_conversation(
            self,
            channel_internal_id: int,
            session_id: uuid.UUID,
            new_messages: list[AgentMessage] | None = None,
            agent: Agent | None = None,
    ):
        request_id = uuid.uuid4()
        chat_id = channel_internal_id
        logger.info(
            f"[{request_id}] Starting conversation for session_id={session_id} chat_id={chat_id}",
        )
        with self.set_current_request_id(request_id):
            user = await self._get_or_create_user(chat_id)
            agent = (
                agent or
                await self.get_agent_for_user(user) or
                self._agent
            )
            for agent_message in new_messages or ():
                await self._sessions_storage.add_message(
                    session_id=session_id,
                    message=agent_message,
                )
            await self._generate_and_send_answer(
                session_id=session_id,
                chat_id=chat_id,
                agent=agent,
                messages=new_messages,
            )
            logger.info(
                f"[{request_id}] Finished conversation for session_id={session_id} chat_id={chat_id}",
            )

    async def handle_new_session(self, message: aiogram.types.Message):
        user = await self._get_or_create_user(message.chat.id)
        session_id = await self._create_new_session(user, message.chat.id)

        agent = await self.get_agent_for_user(user) or self._agent
        printer = AgentMessagePrinter(
            bot=self._bot,
            chat_id=message.chat.id,
            session_id=session_id,
            sessions_storage=self._sessions_storage,
            agent=agent,
            show_context_usage=self._settings.show_context_usage,
            show_costs=self._settings.show_costs,
            debug=self._settings.debug,
        )
        await printer.print(text="Dialog context reset")

    async def handle_voice_message(self, message: aiogram.types.Message):
        request_id = uuid.uuid4()
        logger.info(
            f"[{request_id}] Received voice message event chat_id={message.chat.id}",
        )
        with self.set_current_request_id(request_id):
            user = await self._get_or_create_user(message.chat.id)
            agent = await self.get_agent_for_user(user) or self._agent
            session_id = await self._get_or_create_session(user, message.chat.id)

            await self.reject_all_pending_confirmations(session_id=session_id)

            printer = AgentMessagePrinter(
                bot=self._bot,
                chat_id=message.chat.id,
                session_id=session_id,
                sessions_storage=self._sessions_storage,
                agent=agent,
                show_context_usage=self._settings.show_context_usage,
                show_costs=self._settings.show_costs,
                debug=self._settings.debug,
            )

            if self._stt is None:
                await printer.print(
                    text="Voice messages not supported",
                )
                return

            file = await self._bot.get_file(message.voice.file_id)
            audio_bytes_io = await self._bot.download_file(file.file_path)
            audio_bytes = audio_bytes_io.read()
            audio_format = "ogg"

            await self._sessions_storage.add_message(
                session_id=session_id,
                message=AgentMessage(role="user", audio=audio_bytes, audio_format=audio_format),
            )

            async with printer:
                stt_message = await self._stt.transcribe_bytes(audio_bytes, format=audio_format)
            await self._sessions_storage.add_message(
                session_id=session_id,
                message=stt_message,
            )

            context_info = self._get_message_context(message=message)
            text_with_context = f"""
            {context_info}
            IMPORTANT: It is voice message
            
            ##User message:
            {stt_message.text}
            """

            await self._sessions_storage.add_message(
                session_id=session_id,
                message=AgentMessage(role="stt", text=text_with_context),
            )
            logger.info(
                f"[{request_id}] Starting processing for session_id={session_id} chat_id={message.chat.id}",
            )
            await self._generate_and_send_answer(
                chat_id=message.chat.id,
                session_id=session_id,
                agent=agent,
            )
            logger.info(
                f"[{request_id}] Finished processing for session_id={session_id} chat_id={message.chat.id}",
            )

    async def handle_text_message(self, message: aiogram.types.Message):
        request_id = uuid.uuid4()
        logger.info(
            f"[{request_id}] Received text message event chat_id={message.chat.id}",
        )
        with self.set_current_request_id(request_id):
            user = await self._get_or_create_user(message.chat.id)
            agent = await self.get_agent_for_user(user) or self._agent
            session_id = await self._get_or_create_session(user, message.chat.id)

            await self.reject_all_pending_confirmations(session_id=session_id)

            context_info = self._get_message_context(message=message)
            text_with_context = f"""
            {context_info}
            
            ##User message:
            {message.text}
            """

            await self._sessions_storage.add_message(
                session_id=session_id,
                message=AgentMessage(role="user", text=text_with_context),
            )
            logger.info(
                f"[{request_id}] Starting processing for session_id={session_id} chat_id={message.chat.id}",
            )
            await self._generate_and_send_answer(
                chat_id=message.chat.id,
                session_id=session_id,
                agent=agent,
            )
            logger.info(
                f"[{request_id}] Finished processing for session_id={session_id} chat_id={message.chat.id}",
            )

    async def handle_confirmation_callback(self, callback_query: aiogram.types.CallbackQuery, callback_data: ConfirmationCallbackData):
        request_id = uuid.uuid4()
        logger.info(
            f"[{request_id}] Received confirmation callback event chat_id={callback_query.message.chat.id}",
        )
        with self.set_current_request_id(request_id):
            user = await self._get_or_create_user(callback_query.message.chat.id)
            session_id = await self._get_or_create_session(user, callback_query.message.chat.id)

            confirmation_id = uuid.UUID(callback_data.id)
            approved = callback_data.approved == "yes"
            await self.resolve_confirmation(
                session_id=session_id,
                confirmation_id=confirmation_id,
                approved=approved,
            )

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
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            await callback_query.answer()

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

    async def _generate_and_send_answer(
            self,
            chat_id: int,
            session_id: uuid.UUID,
            agent: Agent,
            messages: list[AgentMessage] | None = None,
    ):
        request_id = uuid.uuid4()
        logger.info(
            f"[{request_id}] Starting generation for session_id={session_id} chat_id={chat_id}",
        )
        saver = AgentMessageSaver(
            sessions_storage=self._sessions_storage,
            session_id=session_id,
        )
        printer = AgentMessagePrinter(
            bot=self._bot,
            chat_id=chat_id,
            session_id=session_id,
            sessions_storage=self._sessions_storage,
            agent=agent,
            show_context_usage=self._settings.show_context_usage,
            show_costs=self._settings.show_costs,
            debug=self._settings.debug,
        )

        async with self._lock_chat_for_generating(chat_id):
            message_generator = self._sessions_storage.get_messages(
                filter=MessageFilter(session_id=session_id),
            )
            messages = [_message async for _message in message_generator]

            with (
                    self.set_current_channel(),
                    self.set_current_chat_id(chat_id),
                    self.set_current_session_id(session_id),
                    self.set_current_request_id(request_id),
            ):
                async with (printer, saver):
                    async for new_message in agent.ask(messages=messages, channel=self):
                        await saver.register_new_message(new_message)
                        await printer.register_new_message(new_message)

                if (
                        await self.summarize_dialog_if_needed(agent=agent, session_id=session_id) and
                        self._settings.debug
                ):
                    await printer.print(text="Dialog summarized")

        logger.info(
            f"[{request_id}] Finished generation for session_id={session_id} chat_id={chat_id}",
        )

    @contextlib.asynccontextmanager
    async def _lock_chat_for_generating(self, chat_id: int):
        lock_key = self._get_chat_generation_lock_key(chat_id)

        try:
            while await self._is_chat_generation_in_progress(chat_id):
                await asyncio.sleep(1)
            await self._syncer.set(lock_key, True, ttl=300)
            yield
        finally:
            await self._syncer.delete(lock_key)

    async def request_confirmation(self, question: str) -> uuid.UUID:
        confirmation_id = uuid.uuid4()
        chat_id = self.get_current_chat_id()
        if chat_id is None:
            raise RuntimeError("chat_id not set in context")

        keyboard = aiogram.types.InlineKeyboardMarkup(inline_keyboard=[
            [
                aiogram.types.InlineKeyboardButton(
                    text="✅ Confirm",
                    callback_data=ConfirmationCallbackData(id=str(confirmation_id), approved="yes").pack()
                ),
                aiogram.types.InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data=ConfirmationCallbackData(id=str(confirmation_id), approved="no").pack()
                ),
            ]
        ])
        await self._bot.send_message(
            chat_id=chat_id,
            text=f"```\n{question}\n```",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return confirmation_id

    async def _get_or_create_user(self, chat_id: int):
        user = await self._users_storage.get_user_by_channel(
            channel_key=self._channel_key,
            channel_internal_id=str(chat_id),
        )
        
        if user:
            return user
        
        user = await self._users_storage.create_user()
        return user

    async def _get_or_create_session(self, user, chat_id: int) -> uuid.UUID:
        session_id = await self._users_storage.get_actual_session(
            user_id=user.id,
            channel_key=self._channel_key,
            channel_internal_id=str(chat_id),
        )
        if session_id is not None:
            return session_id

        return await self._create_new_session(user, chat_id)

    async def _create_new_session(self, user, chat_id: int) -> uuid.UUID:
        session_id = uuid.uuid4()
        await self._sessions_storage.create_session(session_id=session_id)
        await self._users_storage.attach_session_to_user(
            user_id=user.id,
            session_id=session_id,
            channel_key=self._channel_key,
            channel_internal_id=str(chat_id),
        )
        return session_id

    def _get_chat_generation_lock_key(self, chat_id: int) -> str:
        return f"{ChannelTypeEnum.TELEGRAM.value}:{self._channel_key}:generation_lock:chat:{chat_id}"

    async def _is_chat_generation_in_progress(self, chat_id: int) -> bool:
        lock_key = self._get_chat_generation_lock_key(chat_id)
        return await self._syncer.get(lock_key) is not None
