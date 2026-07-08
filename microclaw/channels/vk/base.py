import asyncio
import contextlib
import contextvars
import json
import random
import uuid
from typing import Sequence, Iterable

import aiohttp
from loguru import logger
from vkbottle import Callback, Keyboard
from vkbottle.bot import Bot, Message
from vkbottle_types.events import GroupEventType

from microclaw.agents import Agent
from microclaw.channels.base import BaseChannel
from microclaw.channels.settings import ChannelTypeEnum
from microclaw.channels.utils import AgentMessageSaver
from microclaw.dto import AgentMessage, DecisionEnum
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.sessions_storages.filters import MessageFilter
from microclaw.stt import STT
from microclaw.syncers import SyncerInterface
from microclaw.users_storages import UsersStorageInterface
from microclaw.toolkits import ToolKitSettings
from .settings import VKSettings
from .printer import VKAgentMessagePrinter
from .toolkit import VKToolKit


class BaseVKChannel(BaseChannel):
    MAX_MESSAGE_LENGTH = 4096
    CHAT_ID_CONTEXT = contextvars.ContextVar("chat_id", default=None)

    def __init__(
        self,
        settings: VKSettings,
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

        self._bot = self._create_bot()
        self._setup_handlers()

    def _create_bot(self) -> Bot:
        raise NotImplementedError

    def _setup_handlers(self) -> None:
        self._bot.on.message()(self._handle_message)
        self._bot.on.raw_event(
            GroupEventType.MESSAGE_EVENT,
            dataclass=dict,
        )(self._handle_confirmation_callback)

    def get_toolkit(self) -> VKToolKit:
        toolkit_settings = ToolKitSettings(
            path="microclaw.channels.vk.toolkit.VKToolKit",
            args={"token": self._settings.token},
        )
        return VKToolKit(key="vk_channel", settings=toolkit_settings, bot=self._bot)

    @classmethod
    def get_current_chat_id(cls) -> int | None:
        return cls.CHAT_ID_CONTEXT.get(None)

    @contextlib.contextmanager
    def set_current_chat_id(self, peer_id: int):
        token = self.CHAT_ID_CONTEXT.set(peer_id)
        try:
            yield
        finally:
            self.CHAT_ID_CONTEXT.reset(token)

    async def start(self):
        self.add_task(self.listen_events())

    async def listen_events(self):
        raise NotImplementedError

    async def start_conversation(
        self,
        channel_internal_id: int,
        session_id: uuid.UUID,
        new_messages: Iterable[AgentMessage] = (),
        agent: Agent | None = None,
    ):
        peer_id = channel_internal_id
        request_id = uuid.uuid4()
        with self.set_current_request_id(request_id):
            logger.info(
                f"[{request_id}] Conversation start session={session_id} peer={peer_id}",
            )
            user = await self._get_or_create_user(peer_id)
            agent = agent or await self.get_agent_for_user(user) or self._agent
            await self._generate_and_send_answer(
                session_id=session_id,
                peer_id=peer_id,
                agent=agent,
                new_messages=new_messages,
            )
            logger.info(
                f"[{request_id}] Conversation end session={session_id} peer={peer_id}",
            )

    async def _handle_message(self, message: Message):
        request_id = uuid.uuid4()
        with self.set_current_request_id(request_id):
            logger.info(
                f"[{request_id}] msg from_id={message.from_id} peer_id={message.peer_id} "
                f"text={message.text!r} att={len(message.attachments) if message.attachments else 0}",
            )
            if self._is_auth_disabled(message):
                logger.warning(f"[{request_id}] rejected by allow_from")
                return

            text = (message.text or "").strip()
            if text in ("/reset", "/start"):
                await self.handle_new_session(message)
            elif self._get_audio_message_attachments(message):
                await self.handle_voice_message(message)
            else:
                await self.handle_text_message(message)

    async def handle_new_session(self, message: Message):
        user = await self._get_or_create_user(message.peer_id)
        session_id = await self._create_new_session(user, message.peer_id)
        agent = await self.get_agent_for_user(user) or self._agent
        await self._printer(message.peer_id, session_id, agent).print(
            text="Dialog context reset"
        )

    async def handle_voice_message(self, message: Message):
        request_id = uuid.uuid4()
        with self.set_current_request_id(request_id):
            logger.info(f"[{request_id}] voice peer={message.peer_id}")

            user = await self._get_or_create_user(message.peer_id)
            agent = await self.get_agent_for_user(user) or self._agent
            session_id = await self._get_or_create_session(user, message.peer_id)
            printer = self._printer(message.peer_id, session_id, agent)

            if self._stt is None:
                logger.warning(f"[{request_id}] STT unavailable")
                await printer.print(text="Voice messages not supported")
                return

            audio_attachments = self._get_audio_message_attachments(message)
            if not audio_attachments:
                await printer.print(text="No audio message found")
                return

            audio_bytes = await self._download_audio(audio_attachments[0].link_ogg)

            async with printer:
                stt_message = await self._stt.transcribe_bytes(
                    audio_bytes, format="ogg"
                )

            new_messages = [
                AgentMessage(role="user", audio=audio_bytes, audio_format="ogg"),
                stt_message,
                AgentMessage(
                    role="stt",
                    text=self._format_voice_context(message, stt_message.text),
                ),
            ]
            await self._generate_and_send_answer(
                peer_id=message.peer_id,
                session_id=session_id,
                agent=agent,
                new_messages=new_messages,
            )

    async def handle_text_message(self, message: Message):
        user = await self._get_or_create_user(message.peer_id)
        agent = await self.get_agent_for_user(user) or self._agent
        session_id = await self._get_or_create_session(user, message.peer_id)

        user_message = AgentMessage(
            role="user",
            text=self._format_text_context(message),
        )
        await self._generate_and_send_answer(
            peer_id=message.peer_id,
            session_id=session_id,
            agent=agent,
            new_messages=[user_message],
        )

    async def _handle_confirmation_callback(self, event: dict):
        request_id = uuid.uuid4()
        with self.set_current_request_id(request_id):
            obj = event.get("object", {})
            peer_id = obj.get("peer_id")
            if peer_id is None:
                logger.warning("message_event missing peer_id")
                return

            async with self._lock_chat_for_generating(peer_id):
                payload = obj.get("payload", {})
                if isinstance(payload, str):
                    payload = json.loads(payload)
                payload = payload or {}

                session_id_str = payload.get("session_id")
                approved = payload.get("approved") == "yes"
                if not session_id_str:
                    logger.warning("message_event missing session_id")
                    return

                user = await self._get_or_create_user(peer_id)
                _session_id = uuid.UUID(session_id_str)
                agent = await self.get_agent_for_user(user) or self._agent
                printer = self._printer(peer_id, _session_id, agent)
                saver = AgentMessageSaver(
                    sessions_storage=self._sessions_storage,
                    session_id=_session_id,
                )

                async with printer, saver:
                    async for msg in agent.resume_after_confirmation(
                        session_id=_session_id,
                        decision=DecisionEnum.APPROVE
                        if approved
                        else DecisionEnum.REJECT,
                        channel=self,
                    ):
                        await saver.register_new_message(msg)
                        await printer.register_new_message(msg)

                status_text = "✅ Confirmed" if approved else "❌ Rejected"
                event_id = obj.get("event_id")
                user_id = obj.get("user_id")

                try:
                    await self._bot.api.messages.send_message_event_answer(
                        event_id=event_id,
                        user_id=user_id,
                        peer_id=peer_id,
                        event_data=json.dumps(
                            {"type": "show_snackbar", "text": status_text}
                        ),
                    )
                except Exception:
                    logger.exception("send_message_event_answer failed")

    async def _generate_and_send_answer(
        self,
        peer_id: int,
        session_id: uuid.UUID,
        agent: Agent,
        new_messages: Sequence[AgentMessage] = (),
    ):
        request_id = uuid.uuid4()
        with self.set_current_request_id(request_id):
            logger.info(f"[{request_id}] gen start session={session_id} peer={peer_id}")
            for message in new_messages:
                await self._sessions_storage.add_message(
                    session_id=session_id, message=message
                )

            saver = AgentMessageSaver(
                sessions_storage=self._sessions_storage,
                session_id=session_id,
            )
            printer = self._printer(peer_id, session_id, agent)

            async with self._lock_chat_for_generating(peer_id):
                message_generator = self._sessions_storage.get_messages(
                    filter=MessageFilter(session_id=session_id)
                )
                history = [_message async for _message in message_generator]

                with (
                    self.set_current_channel(),
                    self.set_current_chat_id(peer_id),
                    self.set_current_session_id(session_id),
                ):
                    async with printer, saver:
                        msg_generator = (
                            agent.resume_after_confirmation(
                                session_id=session_id,
                                decision=DecisionEnum.REJECT,
                                new_messages=new_messages,
                                channel=self,
                            )
                            if await agent.has_pending_interrupt(session_id=session_id)
                            else agent.ask(messages=history, channel=self)
                        )
                        async for new_message in msg_generator:
                            if new_message.role == "request_confirmation":
                                entries = json.loads(new_message.text)
                                for entry in entries:
                                    await self._send_confirmation(
                                        entry, peer_id, session_id
                                    )
                                continue
                            await saver.register_new_message(new_message)
                            await printer.register_new_message(new_message)

                    if (
                        await self.summarize_dialog_if_needed(
                            agent=agent, session_id=session_id
                        )
                        and self._settings.debug
                    ):
                        await printer.print(text="Dialog summarized")

            logger.info(f"[{request_id}] gen end session={session_id} peer={peer_id}")

    async def _send_confirmation(
        self, entry: dict, peer_id: int, session_id: uuid.UUID
    ):
        keyboard = Keyboard(inline=True)
        keyboard.add(
            Callback(
                "✅ Confirm",
                payload={"session_id": str(session_id), "approved": "yes"},
            )
        )
        keyboard.row()
        keyboard.add(
            Callback(
                "❌ Cancel",
                payload={"session_id": str(session_id), "approved": "no"},
            )
        )
        await self._bot.api.messages.send(
            peer_id=peer_id,
            message=entry.get("description", ""),
            keyboard=keyboard.get_json(),
            random_id=random.randint(-2147483648, 2147483647),
        )

    def _is_auth_disabled(self, message: Message) -> bool:
        if not self._settings.allow_from:
            return False
        user_set = {
            message.from_id,
            str(message.from_id),
            message.peer_id,
            str(message.peer_id),
        }
        return not (user_set & set(self._settings.allow_from))

    def _get_audio_message_attachments(self, message: Message) -> list:
        if not message.attachments:
            return []
        return [
            att.audio_message
            for att in message.attachments
            if att.type == "audio_message" and att.audio_message
        ]

    def _printer(
        self, peer_id: int, session_id: uuid.UUID, agent: Agent
    ) -> VKAgentMessagePrinter:
        return VKAgentMessagePrinter(
            bot=self._bot,
            peer_id=peer_id,
            session_id=session_id,
            sessions_storage=self._sessions_storage,
            agent=agent,
            show_context_usage=self._settings.show_context_usage,
            show_costs=self._settings.show_costs,
            debug=self._settings.debug,
        )

    async def _download_audio(self, url: str) -> bytes:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.read()

    def _format_text_context(self, message: Message) -> str:
        return (
            f"{self._get_message_context(message)}\n\n## User message:\n{message.text}"
        )

    def _format_voice_context(self, message: Message, transcribed: str) -> str:
        return (
            f"{self._get_message_context(message)}\n"
            "IMPORTANT: It is voice message\n"
            "\n"
            "## User message:\n"
            f"{transcribed}"
        )

    def _get_message_context(self, message: Message) -> str:
        return (
            "## Chat Info\n"
            f"Peer ID: {message.peer_id}\n"
            "\n"
            "## User Info\n"
            f"ID: {message.from_id}\n"
            "\n"
            "## Message Info\n"
            f"ID: {message.message_id}\n"
            f"Date: {message.date.isoformat() if getattr(message, 'date', None) else None}\n"
        )

    @contextlib.asynccontextmanager
    async def _lock_chat_for_generating(self, peer_id: int):
        lock_key = self._get_chat_generation_lock_key(peer_id)
        try:
            while await self._is_chat_generation_in_progress(peer_id):
                await asyncio.sleep(1)
            await self._syncer.set(lock_key, True, ttl=300)
            yield
        finally:
            await self._syncer.delete(lock_key)

    async def _get_or_create_user(self, peer_id: int):
        user = await self._users_storage.get_user_by_channel(
            channel_key=self._channel_key,
            channel_internal_id=str(peer_id),
        )
        return user or await self._users_storage.create_user()

    async def _get_or_create_session(self, user, peer_id: int) -> uuid.UUID:
        session_id = await self._users_storage.get_actual_session(
            user_id=user.id,
            channel_key=self._channel_key,
            channel_internal_id=str(peer_id),
        )
        return session_id or await self._create_new_session(user, peer_id)

    async def _create_new_session(self, user, peer_id: int) -> uuid.UUID:
        session_id = uuid.uuid4()
        await self._sessions_storage.create_session(session_id=session_id)
        await self._users_storage.attach_session_to_user(
            user_id=user.id,
            session_id=session_id,
            channel_key=self._channel_key,
            channel_internal_id=str(peer_id),
        )
        return session_id

    def _get_chat_generation_lock_key(self, peer_id: int) -> str:
        return f"{ChannelTypeEnum.VK.value}:{self._channel_key}:generation_lock:chat:{peer_id}"

    async def _is_chat_generation_in_progress(self, peer_id: int) -> bool:
        return (
            await self._syncer.get(self._get_chat_generation_lock_key(peer_id))
            is not None
        )
