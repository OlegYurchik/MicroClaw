import contextlib
import contextvars
import json
import random
import uuid

from .middlewares.typing import VKTypingMiddleware
from .printer import VKAgentMessagePrinter
from .settings import VKSettings
from .toolkit import VKToolKit
import aiohttp
from aiohttp import ClientError
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from vkbottle.bot import Bot, Message
from vkbottle.exception_factory import VKAPIError
from vkbottle.tools.event_data import ShowSnackbarEvent
from vkbottle_types.events import GroupEventType

from microclaw.agents import Agent
from microclaw.channels.base import BaseChannel
from microclaw.dto import AgentMessage, DecisionEnum
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.stt import STT
from microclaw.syncers import SyncerInterface
from microclaw.toolkits import ToolKitSettings
from microclaw.users_storages import UsersStorageInterface
from microclaw.utils.context import get_current_request_id, set_current_request_id


class BaseVKChannel(BaseChannel):
    r"""Format responses using VK Markdown subset for inline formatting.

    YOU are responsible for correct formatting. Use ONLY these constructs:
    - **bold**
    - *italic* (or _italic_)
    - <u>underline</u>
    - [label](https://example.com)

    VK does NOT support: headers (#), lists (- * 1.), code blocks, ~strikethrough~,
    ||spoiler||, quotes, HTML tags. Do NOT use them.

    Escape literal * _ [ ] ( ) with backslash when they should appear as-is.
    Nesting is supported: ***bold+italic***.

    If your escaping is wrong, the message may be sent as plain text instead.
    """
    MAX_MESSAGE_LENGTH = 4096
    CHAT_ID_CONTEXT = contextvars.ContextVar("chat_id", default=None)
    QUEUED_MESSAGE_TEXT = "⏳ Message queued"

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
        self._printers: dict[str, VKAgentMessagePrinter] = {}

    def _create_bot(self) -> Bot:
        raise NotImplementedError

    def _setup_handlers(self) -> None:
        message_view = self._bot.labeler.views()["message"]
        message_view.register_middleware(VKTypingMiddleware)
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

    async def handle_new_session(self, message: Message):
        await super().handle_new_session(message.peer_id)

    async def _handle_message(self, message: Message):
        request_id = uuid.uuid4()
        with set_current_request_id(request_id):
            if self._is_auth_disabled(message):
                return

            text = (message.text or "").strip()
            payload = message.payload or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = {}
            payload = payload or {}

            if text == "/start" or payload.get("command") == "reset":
                await self.handle_new_session(message)
            elif self._get_audio_message_attachments(message):
                await self.handle_voice_message(message)
            else:
                await self.handle_text_message(message)

    async def handle_voice_message(self, message: Message):
        peer_id = message.peer_id
        user = await self._get_or_create_user(peer_id)
        agent = await self.get_agent_for_user(user) or self._agent

        if self._stt is None:
            logger.warning(f"[{get_current_request_id()}] STT unavailable")
            _send = retry(
                retry=retry_if_exception_type((ClientError, VKAPIError)),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
            )(self._bot.api.messages.send)
            await _send(
                peer_id=peer_id,
                message="Voice messages not supported",
                random_id=random.randint(-2147483648, 2147483647),
            )
            return

        audio_attachments = self._get_audio_message_attachments(message)
        if not audio_attachments:
            _send = retry(
                retry=retry_if_exception_type((ClientError, VKAPIError)),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
            )(self._bot.api.messages.send)
            await _send(
                peer_id=peer_id,
                message="No audio message found",
                random_id=random.randint(-2147483648, 2147483647),
            )
            return

        audio_bytes = await self._download_audio(audio_attachments[0].link_ogg)
        stt_message = await self._stt.transcribe_bytes(audio_bytes, format="ogg")

        new_messages = [
            AgentMessage(role="user", audio=audio_bytes, audio_format="ogg"),
            stt_message,
            AgentMessage(
                role="stt",
                text=self._format_voice_context(message, stt_message.text),
            ),
        ]
        await self._enqueue_and_process(
            chat_id=peer_id,
            new_messages=new_messages,
            agent=agent,
        )

    async def handle_text_message(self, message: Message):
        peer_id = message.peer_id
        user = await self._get_or_create_user(peer_id)
        agent = await self.get_agent_for_user(user) or self._agent

        user_message = AgentMessage(
            role="user",
            text=self._format_text_context(message),
        )
        await self._enqueue_and_process(
            chat_id=peer_id,
            new_messages=[user_message],
            agent=agent,
        )

    async def _handle_confirmation_callback(self, event: dict):
        request_id = uuid.uuid4()
        with set_current_request_id(request_id):
            obj = event.get("object", {})
            peer_id = obj.get("peer_id")
            if peer_id is None:
                logger.warning("message_event missing peer_id")
                return

            async with self._lock_chat_for_processing(peer_id):
                payload = obj.get("payload", {})
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        payload = {}
                payload = payload or {}

                session_id_str = payload.get("session_id")
                approved = payload.get("approved") == "yes"
                if not session_id_str:
                    logger.warning("message_event missing session_id")
                    return

                user = await self._get_or_create_user(peer_id)
                session_id = uuid.UUID(session_id_str)
                agent = await self.get_agent_for_user(user) or self._agent

                status_text = "✅ Confirmed" if approved else "❌ Rejected"
                event_id = obj.get("event_id")
                user_id = obj.get("user_id")

                event_data = ShowSnackbarEvent(text=status_text)

                _send_event_answer = retry(
                    retry=retry_if_exception_type((ClientError, VKAPIError)),
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=1, max=10),
                    reraise=True,
                )(self._bot.api.messages.send_message_event_answer)

                await _send_event_answer(
                    event_id=event_id,
                    user_id=user_id,
                    peer_id=peer_id,
                    event_data=event_data.model_dump_json(),
                )

                conversation_message_id = obj.get("conversation_message_id")
                if conversation_message_id:
                    await self._update_confirmation_message(
                        peer_id=peer_id,
                        conversation_message_id=conversation_message_id,
                        approved=approved,
                    )

                decision = DecisionEnum.APPROVE if approved else DecisionEnum.REJECT
                await self._process_batch(
                    chat_id=peer_id,
                    session_id=session_id,
                    agent=agent,
                    batch=[],
                    decision=decision,
                )

    async def _update_confirmation_message(
        self,
        peer_id: int,
        conversation_message_id: int,
        approved: bool,
    ):
        status_line = "✅ Confirmed" if approved else "❌ Rejected"

        _get_by_cmid = retry(
            retry=retry_if_exception_type((ClientError, VKAPIError)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(self._bot.api.messages.get_by_conversation_message_id)

        response = await _get_by_cmid(
            peer_id=peer_id,
            conversation_message_ids=conversation_message_id,
        )
        current_text = ""
        if response.items:
            current_text = response.items[0].text or ""

        if status_line in current_text:
            return

        new_text = f"{current_text}\n\n{status_line}" if current_text else status_line

        _edit = retry(
            retry=retry_if_exception_type((ClientError, VKAPIError)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(self._bot.api.messages.edit)

        await _edit(
            peer_id=peer_id,
            conversation_message_id=conversation_message_id,
            message=new_text,
            keyboard="",
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
        async def _fetch():
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.read()

        _fetch_with_retry = retry(
            retry=retry_if_exception_type(ClientError),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(_fetch)

        return await _fetch_with_retry()

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
            f"Message ID: {message.id}\n"
            f"Conversation Message ID: {message.conversation_message_id}\n"
            f"Date: {message.date.isoformat() if getattr(message, 'date', None) else None}\n"
        )

    async def _on_message_queued(self, chat_id: str | int) -> None:
        try:
            plain_text, format_data = VKAgentMessagePrinter._apply_vk_formatting(
                self.QUEUED_MESSAGE_TEXT
            )
            kwargs: dict = {
                "peer_id": int(chat_id),
                "message": plain_text,
                "random_id": random.randint(-2147483648, 2147483647),
            }
            if format_data:
                kwargs["format_data"] = format_data
            _send = retry(
                retry=retry_if_exception_type((ClientError, VKAPIError)),
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
            )(self._bot.api.messages.send)
            await _send(**kwargs)
        except Exception:
            logger.opt(exception=True).warning("Failed to send queued notification")

    def _get_printer(self, chat_id: str | int) -> VKAgentMessagePrinter | None:
        return self._printers.get(str(chat_id))
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
        printer = self._printer(int(chat_id), session_id, agent)
        self._printers[cid] = printer
        async with printer:
            try:
                yield
            finally:
                self._printers.pop(cid, None)

    async def _send_system_message(self, chat_id: str | int, text: str) -> None:
        _send = retry(
            retry=retry_if_exception_type((ClientError, VKAPIError)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )(self._bot.api.messages.send)

        plain_text, format_data = VKAgentMessagePrinter._apply_vk_formatting(text)
        kwargs: dict = {
            "peer_id": int(chat_id),
            "message": plain_text,
            "random_id": random.randint(-2147483648, 2147483647),
        }
        if format_data:
            kwargs["format_data"] = format_data
        await _send(**kwargs)
