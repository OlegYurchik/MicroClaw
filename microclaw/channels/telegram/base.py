import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import aiogram
import facet
import contextvars
from aiogram.enums import ParseMode
from aiogram.filters.callback_data import CallbackData

from microclaw.agents import Agent
from microclaw.channels.base import BaseChannel
from microclaw.channels.settings import ChannelTypeEnum
from microclaw.channels.utils import AgentMessageSaver
from microclaw.dto import AgentMessage
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.stt import STT
from microclaw.syncers import SyncerInterface
from microclaw.users_storages import UsersStorageInterface
from microclaw.toolkits import ToolKitSettings
from .middlewares.auth import AuthMiddleware
from .middlewares.typing import TypingMiddleware
from .printer import AgentMessagePrinter
from .settings import TelegramSettings
from .toolkit import TelegramToolKit


@dataclass
class QueuedMessage:
    session_id: uuid.UUID
    text: str
    chat_id: int


class ConfirmationCallbackData(CallbackData, prefix="confirm"):
    id: str
    approved: str


class BaseTelegramChannel(facet.AsyncioServiceMixin, BaseChannel):
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
            resolver: "DependencyResolver",
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

        self._bot = aiogram.Bot(token=settings.token)
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

    async def start(self):
        try:
            await self._bot.set_my_name(name=self._settings.name)
        except Exception:
            pass

        commands = [
            aiogram.types.BotCommand(
                command="reset",
                description="Dialog context reset",
            ),
        ]
        try:
            await self._bot.set_my_commands(commands)
        except Exception:
            pass

        self.add_task(self.listen_events())

    @contextmanager
    def _set_channel_context(self, chat_id: int):
        channel_token = self.CHANNEL_CONTEXT.set(self)
        chat_id_token = self.CHAT_ID_CONTEXT.set(chat_id)
        try:
            yield
        finally:
            self.CHANNEL_CONTEXT.reset(channel_token)
            self.CHAT_ID_CONTEXT.reset(chat_id_token)

    async def start_conversation(
            self,
            channel_internal_id: int,
            session_id: uuid.UUID | None = None,
            messages: list[AgentMessage] | None = None,
            agent: Agent | None = None,
    ):
        chat_id = channel_internal_id
        with self._set_channel_context(chat_id):
            user = await self._users_storage.get_user_by_channel(
                channel_key=self._channel_key,
                channel_internal_id=str(chat_id),
            )
            agent = agent or await self.get_agent_for_user(user) or self._agent

            for agent_message in messages or []:
                await self._sessions_storage.add_message(
                    session_id=session_id,
                    message=agent_message,
                )
            message_generator = self._sessions_storage.get_messages(session_id=session_id)
            all_messages = [message async for message in message_generator]

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

            async with (printer.catch_exception(), printer, saver):
                async for new_message in agent.ask(messages=all_messages, channel=self, stream=True):
                    await saver.register_new_message(new_message)
                    await printer.register_new_message(new_message)
        
    async def listen_events(self):
        raise NotImplementedError

    async def handle_new_session(self, message: aiogram.types.Message):
        user = await self._get_or_create_user(message)
        session_id = await self._create_new_session(user, message)

        printer = AgentMessagePrinter(
            bot=self._bot,
            chat_id=message.chat.id,
            session_id=session_id,
            sessions_storage=self._sessions_storage,
            agent=self._agent,
            show_context_usage=self._settings.show_context_usage,
            show_costs=self._settings.show_costs,
            debug=self._settings.debug,
        )
        await printer.print(text="Dialog context reset")

    async def handle_voice_message(self, message: aiogram.types.Message):
        user = await self._get_or_create_user(message)
        session_id = await self._get_or_create_session(user, message)

        saver = AgentMessageSaver(
            sessions_storage=self._sessions_storage,
            session_id=session_id,
        )
        printer = AgentMessagePrinter(
            bot=self._bot,
            chat_id=message.chat.id,
            session_id=session_id,
            sessions_storage=self._sessions_storage,
            agent=self._agent,
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

        async with printer.catch_exception():
            stt_message = await self._stt.transcribe_bytes(audio_bytes, format=audio_format)
        await self._sessions_storage.add_message(
            session_id=session_id,
            message=stt_message,
        )

        context_info = self.get_message_context(message=message)
        text_with_context = f"""
        {context_info}
        
        ##User message:
        {stt_message.text}
        """

        await self._sessions_storage.add_message(
            session_id=session_id,
            message=AgentMessage(role="stt", text=text_with_context),
        )
        await self.handle_text(message=message, session_id=session_id, text=text_with_context)

    async def handle_text_message(self, message: aiogram.types.Message):
        user = await self._get_or_create_user(message)
        session_id = await self._get_or_create_session(user, message)

        context_info = self.get_message_context(message=message)
        text_with_context = f"""
        {context_info}
        
        ##User message:
        {message.text}
        """

        await self._sessions_storage.add_message(
            session_id=session_id,
            message=AgentMessage(role="user", text=text_with_context),
        )
        await self.handle_text(message=message, session_id=session_id, text=text_with_context)

    async def handle_text(
            self,
            message: aiogram.types.Message | None,
            session_id: uuid.UUID,
            text: str,
            chat_id: int | None = None,
    ):
        if chat_id is None:
            chat_id = message.chat.id

        if await self._is_chat_generation_in_progress(chat_id):
            await self._add_message_to_queue(chat_id, session_id, text)
            await self._show_queue_notification(chat_id)
            return

        lock_key = self._get_chat_generation_lock_key(chat_id)
        await self._syncer.set(lock_key, True, ttl=300)

        try:
            with self._set_channel_context(chat_id):
                user = await self._users_storage.get_user_by_channel(
                    channel_key=self._channel_key,
                    channel_internal_id=str(chat_id),
                )
                agent = await self.get_agent_for_user(user)
                agent = agent or self._agent

                message_generator = self._sessions_storage.get_messages(session_id=session_id)
                messages = [_message async for _message in message_generator]

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

                async with (printer.catch_exception(), saver, printer):
                    async for new_message in agent.ask(messages=messages, channel=self):
                        await saver.register_new_message(new_message)
                        await printer.register_new_message(new_message)

                if (
                        await self.summarize_dialog_if_needed(session_id=session_id) and
                        self._settings.debug
                ):
                    await printer.print(text="Dialog summarized")
        finally:
            await self._syncer.delete(lock_key)
            await self._process_message_queue(chat_id)

    def get_message_context(self, message: aiogram.types.Message) -> str:
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

    async def request_confirmation(self, question: str) -> uuid.UUID:
        confirmation_id = uuid.uuid4()
        chat_id = self.CHAT_ID_CONTEXT.get()
        if chat_id is None:
            raise RuntimeError("chat_id not set in context")

        keyboard = aiogram.types.InlineKeyboardMarkup(inline_keyboard=[
            [
                aiogram.types.InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=ConfirmationCallbackData(id=str(confirmation_id), approved="yes").pack()
                ),
                aiogram.types.InlineKeyboardButton(
                    text="❌ Отменить",
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

    async def handle_confirmation_callback(self, callback_query: aiogram.types.CallbackQuery, callback_data: ConfirmationCallbackData):
        confirmation_id = uuid.UUID(callback_data.id)
        approved = callback_data.approved == "yes"
        await self.resolve_confirmation(confirmation_id, approved)

        await callback_query.answer()

    async def _get_or_create_user(self, message: aiogram.types.Message):
        user = await self._users_storage.get_user_by_channel(
            channel_key=self._channel_key,
            channel_internal_id=str(message.chat.id),
        )
        
        if user:
            return user
        
        user = await self._users_storage.create_user()
        return user

    async def _get_or_create_session(self, user, message: aiogram.types.Message) -> uuid.UUID:
        session_id = await self._users_storage.get_actual_session(
            user_id=user.id,
            channel_key=self._channel_key,
            channel_internal_id=str(message.chat.id),
        )
        if session_id is not None:
            return session_id

        return await self._create_new_session(user, message)

    async def _create_new_session(self, user, message: aiogram.types.Message) -> uuid.UUID:
        session_id = uuid.uuid4()
        await self._sessions_storage.create_session(session_id=session_id)
        await self._users_storage.attach_session_to_user(
            user_id=user.id,
            session_id=session_id,
            channel_key=self._channel_key,
            channel_internal_id=str(message.chat.id),
        )
        return session_id

    def _get_chat_generation_lock_key(self, chat_id: int) -> str:
        return f"{ChannelTypeEnum.TELEGRAM.value}:{self._channel_key}:generation_lock:chat:{chat_id}"

    async def _is_chat_generation_in_progress(self, chat_id: int) -> bool:
        lock_key = self._get_chat_generation_lock_key(chat_id)
        return await self._syncer.get(lock_key) is not None

    def _get_message_queue_key(self, chat_id: int) -> str:
        return f"{ChannelTypeEnum.TELEGRAM.value}:{self._channel_key}:message_queue:{chat_id}"

    async def _add_message_to_queue(self, chat_id: int, session_id: uuid.UUID, text: str) -> None:
        queue_key = self._get_message_queue_key(chat_id)
        queued_message = QueuedMessage(session_id=session_id, text=text, chat_id=chat_id)
        
        queue = await self._syncer.get(queue_key)
        if queue is None:
            queue = []
        queue.append(queued_message)
        await self._syncer.set(queue_key, queue, ttl=3600)

    async def _get_message_queue(self, chat_id: int) -> list[QueuedMessage]:
        queue_key = self._get_message_queue_key(chat_id)
        queue = await self._syncer.get(queue_key)
        return queue if queue is not None else []

    async def _clear_message_queue(self, chat_id: int) -> None:
        queue_key = self._get_message_queue_key(chat_id)
        await self._syncer.delete(queue_key)

    async def _process_message_queue(self, chat_id: int) -> None:
        queue = await self._get_message_queue(chat_id)
        if not queue:
            return

        queued_message = queue[0]
        remaining_queue = queue[1:]
        
        queue_key = self._get_message_queue_key(chat_id)
        if remaining_queue:
            await self._syncer.set(queue_key, remaining_queue, ttl=3600)
        else:
            await self._syncer.delete(queue_key)

        await self._sessions_storage.add_message(
            session_id=queued_message.session_id,
            message=AgentMessage(role="user", text=queued_message.text),
        )
        await self.handle_text(
            message=None,
            session_id=queued_message.session_id,
            text=queued_message.text,
            chat_id=queued_message.chat_id,
        )

    async def _show_queue_notification(self, chat_id: int) -> None:
        await self._bot.answer_chat_query(
            chat_id=chat_id,
            text="⏳ Your message is queued. Response will be generated after the current request completes.",
            show_alert=True,
        )