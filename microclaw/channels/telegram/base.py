import uuid
from collections import defaultdict

import aiogram
import facet

from microclaw.agents import Agent
from microclaw.channels.interfaces import ChannelInterface
from microclaw.channels.utils import AgentMessageSaver
from microclaw.dto import AgentMessage
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.stt import STT
from microclaw.toolkits import ToolKitSettings
from .middlewares.auth import AuthMiddleware
from .middlewares.typing import TypingMiddleware
from .printer import AgentMessagePrinter
from .settings import TelegramSettings
from .toolkit import TelegramToolKit


class BaseTelegramChannel(facet.AsyncioServiceMixin, ChannelInterface):
    """Telegram messenger channel.

    Communication happens in a messenger environment. Keep responses concise and brief.
    Use markdown formatting for text. Do not use tables, schemes or diagrams in your responses.
    """

    END_PHRASE = "NO_REPLY"
    TYPING_ACTION_DELAY = 3
    MAX_MESSAGE_LENGTH = 4096

    def __init__(
            self,
            settings: TelegramSettings,
            agent: Agent,
            sessions_storage: SessionsStorageInterface,
            stt: STT | None = None,
            channel_key: str = "default",
    ):
        super().__init__(
            settings=settings,
            agent=agent,
            sessions_storage=sessions_storage,
            stt=stt,
            channel_key=channel_key,
        )

        self._bot = aiogram.Bot(token=settings.token)
        self._dispatcher = aiogram.Dispatcher()
        self._dispatcher.message.middleware(AuthMiddleware(allow_from=self._settings.allow_from))
        self._dispatcher.message.middleware(TypingMiddleware(delay=self.TYPING_ACTION_DELAY))
        self._dispatcher.message(aiogram.filters.Command("reset"))(self.handle_new_session)
        self._dispatcher.message(aiogram.filters.Command("start"))(self.handle_new_session)
        self._dispatcher.message(aiogram.F.voice)(self.handle_voice_message)
        self._dispatcher.message()(self.handle_text_message)

        self._user_sessions: dict[str, uuid.UUID] = defaultdict(uuid.uuid4)

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

    async def start_conversation(
            self,
            session_id: uuid.UUID,
            messages: list[AgentMessage],
            chat_id: int,
    ):
        for agent_message in messages:
            await self._sessions_storage.add_message(
                session_id=session_id,
                message=agent_message,
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
            agent=self._agent,
            show_context_usage=self._settings.show_context_usage,
            show_costs=self._settings.show_costs,
            debug=self._settings.debug,
        )

        user_session_key = None
        async with (printer.catch_exception(), printer, saver):
            async for new_message in self._agent.ask(messages=messages, channel=self):
                if user_session_key is None:
                    user_session_key = self.generate_user_session_key(chat_id=chat_id)
                    self._user_sessions[user_session_key] = session_id
                await saver.register_new_message(new_message)
                await printer.register_new_message(new_message) 
        
    async def listen_events(self):
        raise NotImplementedError

    async def handle_new_session(self, message: aiogram.types.Message):
        user_session_key = self.generate_user_session_key(message=message)
        session_id = uuid.uuid4()
        self._user_sessions[user_session_key] = session_id

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
        user_session_key = self.generate_user_session_key(message=message)
        session_id = self._user_sessions[user_session_key]

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
        user_session_key = self.generate_user_session_key(message=message)
        session_id = self._user_sessions[user_session_key]

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
            message: aiogram.types.Message,
            session_id: uuid.UUID,
            text: str,
    ):
        message_generator = self._sessions_storage.get_messages(session_id=session_id)
        messages = [_message async for _message in message_generator]

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

        async with (printer.catch_exception(), saver, printer):
            async for new_message in self._agent.ask(messages=messages, channel=self):
                await saver.register_new_message(new_message)
                await printer.register_new_message(new_message)

        if (
                await self.summarize_dialog_if_needed(session_id=session_id) and
                self._settings.debug
        ):
            await printer.print(text="Dialog summarized")

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

    def generate_user_session_key(
            self,
            message: aiogram.types.Message | None = None,
            chat_id: int | None = None,
    ) -> str:
        if chat_id is not None:
            return str(chat_id)
        if message is not None:
            return str(message.chat.id)
        raise ValueError("One of args (message or chat_id) must be defined")
