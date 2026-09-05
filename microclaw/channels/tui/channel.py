import asyncio
import contextlib
import sys
import uuid

from .printer import AgentMessagePrinter
from .settings import TUIChannelSettings
from .ui import RoleEnum, TUIApp
from .ui.widgets.slash_commands import BaseSlashCommand, ExitCommand
from loguru import logger
from pydantic import BaseModel, ConfigDict

from microclaw.agents import Agent
from microclaw.channels.base import BaseChannel
from microclaw.dto import AgentMessage, DecisionEnum, User
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.syncers import SyncerInterface
from microclaw.users_storages import UsersStorageInterface
from microclaw.users_storages.dto import UserCreate
from microclaw.users_storages.filters import UserChannelFilter, UserFilter
from microclaw.utils.context import set_current_request_id


class SlashCommandContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    app: TUIApp
    channel: "TUIChannel"
    raw_text: str


class TUIChannel(BaseChannel):
    CHANNEL_INTERNAL_ID = "tui"

    def __init__(
        self,
        settings: TUIChannelSettings,
        agent: Agent,
        sessions_storage: SessionsStorageInterface,
        syncer: SyncerInterface,
        users_storage: UsersStorageInterface,
        resolver: "DependencyResolver",  # noqa: F821
        channel_key: str = "default",
    ):
        super().__init__(
            settings=settings,
            agent=agent,
            sessions_storage=sessions_storage,
            channel_key=channel_key,
            syncer=syncer,
            users_storage=users_storage,
            resolver=resolver,
        )

        self._user: User | None = None
        self._slash_commands: list[BaseSlashCommand] = [
            ExitCommand(),
        ]
        self._app = TUIApp(channel=self)
        self._processing_lock = asyncio.Lock()
        self._pending_user_messages: list[str] = []
        self._app_task: asyncio.Task | None = None
        self._printers: dict[str | int, AgentMessagePrinter] = {}

    @property
    def app(self) -> TUIApp:
        return self._app

    @property
    def user(self) -> User | None:
        return self._user

    @property
    def slash_commands(self) -> list[BaseSlashCommand]:
        return self._slash_commands

    async def start(self):
        self._user = None
        channel = await self._users_storage.get_user_channel(
            filter_=UserChannelFilter(
                channel_key={self._channel_key},
                channel_internal_id={self.CHANNEL_INTERNAL_ID},
            )
        )
        if channel is not None:
            self._user = await self._users_storage.get_user(
                filter_=UserFilter(id={channel.user_id})
            )
        if self._user is None:
            self._user = await self._users_storage.create_user(data=UserCreate())

        for handler_id, handler in list(logger._core.handlers.items()):
            sink = handler._sink
            if hasattr(sink, "_stream") and sink._stream is sys.stderr:
                logger.remove(handler_id)
                break

        self._app_task = self.add_task(self._app.run_async())

    async def run(self) -> None:
        async with self:
            if self._app_task is None:
                raise RuntimeError("TUI app task not started. Ensure start() was called.")
            await self._app_task

    async def handle_user_message(self, text: str, agent: Agent | None = None) -> None:
        text = text.strip()

        parts = text.split()
        if parts:
            cmd_token = parts[0].lower()
            for cmd in self._slash_commands:
                all_names = [cmd.NAME.lower()] + [a.lower() for a in cmd.ALIASES]
                if cmd_token in all_names:
                    ctx = SlashCommandContext(app=self._app, channel=self, raw_text=text)
                    await cmd.execute(ctx)
                    return

        if self._processing_lock.locked():
            self._pending_user_messages.append(text)
            await self._app.set_queued_messages(self._pending_user_messages)
        else:
            await self._app.add_message(role=RoleEnum.USER, text=text)

        request_id = uuid.uuid4()
        with set_current_request_id(request_id):
            user_message = AgentMessage(role="user", text=text)
            agent = agent or await self.get_agent_for_user(self._user) or self._agent
            async with self._processing_lock:
                await self._enqueue_and_process(
                    chat_id=self.CHANNEL_INTERNAL_ID,
                    new_messages=[user_message],
                    agent=agent,
                    stream=True,
                )

    async def _handle_confirmation_callback(self, session_id: uuid.UUID, approved: bool):
        request_id = uuid.uuid4()
        agent = self._agent

        with set_current_request_id(request_id):
            async with self._processing_lock:
                async with self._lock_chat_for_processing(self.CHANNEL_INTERNAL_ID):
                    decision = DecisionEnum.APPROVE if approved else DecisionEnum.REJECT
                    await self._process_batch(
                        chat_id=self.CHANNEL_INTERNAL_ID,
                        session_id=session_id,
                        agent=agent,
                        batch=[],
                        decision=decision,
                        stream=True,
                    )

    async def _resolve_session_for_chat(self, chat_id: str | int) -> uuid.UUID:
        return await super()._resolve_session_for_chat(chat_id)

    @contextlib.asynccontextmanager
    async def _on_processing(
        self,
        chat_id: str | int,
        session_id: uuid.UUID,
        agent: Agent,
    ):
        printer = AgentMessagePrinter(
            app=self._app,
            session_id=session_id,
            sessions_storage=self._sessions_storage,
            agent=agent,
            debug=self._settings.debug,
        )
        cid = str(chat_id)
        self._printers[cid] = printer
        async with printer:
            try:
                yield
            finally:
                self._printers.pop(cid, None)

    async def _on_agent_message(
        self,
        chat_id: str | int,
        session_id: uuid.UUID,
        agent: Agent,
        msg: AgentMessage,
    ) -> None:
        printer = self._printers.get(str(chat_id))
        if printer is not None:
            await printer.register_new_message(msg)

    async def _on_confirmation_request(
        self,
        chat_id: str | int,
        session_id: uuid.UUID,
        agent: Agent,
        entries: list[dict],
    ) -> None:
        printer = self._printers.get(str(chat_id))
        if printer is not None:
            for entry in entries:
                await printer._send_confirmation(entry)

    async def _send_system_message(self, chat_id: str | int, text: str) -> None:
        await self._app.add_message(role=RoleEnum.SYSTEM, text=text)

    async def print_spent(self):
        if self._user is None:
            return
        session_id = await self._users_storage.get_actual_session(
            user_id=self._user.id,
            channel_key=self._channel_key,
            channel_internal_id=self.CHANNEL_INTERNAL_ID,
        )
        if session_id is None:
            return

        printer = AgentMessagePrinter(
            app=self._app,
            session_id=session_id,
            sessions_storage=self._sessions_storage,
            agent=self._agent,
            debug=self._settings.debug,
        )
        await printer.print_spent()


SlashCommandContext.model_rebuild()
