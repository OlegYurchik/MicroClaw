import datetime
import json
import uuid

from microclaw.agents import Agent
from microclaw.channels.base import BaseChannel
from microclaw.channels.utils import AgentMessageSaver
from microclaw.dto import AgentMessage, DecisionEnum, User
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.sessions_storages.filters import MessageFilter
from pydantic_filters.pagination import OffsetPagination as BasePagination
from microclaw.syncers import SyncerInterface
from microclaw.users_storages import UsersStorageInterface
from .printer import AgentMessagePrinter
from .settings import CLIChannelSettings
from .ui import CLIApp, RoleEnum


class CLIChannel(BaseChannel):
    CHANNEL_INTERNAL_ID = "cli"

    def __init__(
            self,
            settings: CLIChannelSettings,
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
        self._session_id: uuid.UUID | None = None
        self._app = CLIApp(channel=self)

    async def start(self):
        self._user = await self._users_storage.get_user_by_channel(
            channel_key=self._channel_key,
            channel_internal_id=self.CHANNEL_INTERNAL_ID,
        )
        if self._user is None:
            self._user = await self._users_storage.create_user()

        self.add_task(self._app.run_async())

    async def start_conversation(
            self,
            channel_internal_id: str,
            session_id: uuid.UUID,
            new_messages: list[AgentMessage],
            agent: Agent | None = None,
    ):
        for agent_message in new_messages or []:
            await self._sessions_storage.add_message(
                session_id=session_id,
                message=agent_message,
            )
        await self._generate_and_send_answer(agent=agent, session_id=session_id)

    async def handle_user_message(self, text: str, agent: Agent | None = None) -> None:
        if self._session_id is None:
            self._session_id = await self._create_session()

        await self.reject_all_pending_confirmations(session_id=self._session_id)

        user_message = AgentMessage(role="user", text=text)

        await self._sessions_storage.add_message(
            session_id=self._session_id,
            message=user_message,
        )
        await self._generate_and_send_answer(agent=agent)

    async def _generate_and_send_answer(self, agent: Agent | None = None, session_id: uuid.UUID | None = None):
        agent = (
            agent or
            await self.get_agent_for_user(self._user) or
            self._agent
        )

        session_id = session_id or self._session_id

        printer = AgentMessagePrinter(
            app=self._app,
            session_id=session_id,
            sessions_storage=self._sessions_storage,
            agent=agent,
            show_context_usage=self._settings.show_context_usage,
            show_costs=self._settings.show_costs,
            debug=self._settings.debug,
        )
        saver = AgentMessageSaver(
            sessions_storage=self._sessions_storage,
            session_id=session_id,
        )

        message_generator = self._sessions_storage.get_messages(filter=MessageFilter(session_id=session_id))
        messages = [_message async for _message in message_generator]

        with (
                self.set_current_channel(),
                self.set_current_session_id(session_id),
        ):
            await printer.show_thinking()
            async with (printer, saver):
                async for new_message in agent.ask(messages=messages, channel=self, stream=True):
                    if new_message.role == "request_confirmation":
                        entries = json.loads(new_message.text)
                        for entry in entries:
                            await self._send_confirmation(entry, session_id)
                    else:
                        await saver.register_new_message(new_message)
                        await printer.register_new_message(new_message)

            async with printer:
                if (
                        agent.is_summarization_enabled() and
                        await self.is_context_went_across_threshold(
                            agent=agent,
                            session_id=session_id,
                        )
                ):
                    await self._app.add_message(role=RoleEnum.SYSTEM, text="[dim]Summarizing...[/dim]")
                    await self.summarize_dialog_if_needed(agent=agent, session_id=session_id)
                    await self._app.update_message(role=RoleEnum.SYSTEM, text="Dialog summarized")

    async def print_spent(self):
        if self._session_id is None:
            return

        printer = AgentMessagePrinter(
            app=self._app,
            session_id=self._session_id,
            sessions_storage=self._sessions_storage,
            agent=self._agent,
            show_context_usage=self._settings.show_context_usage,
            show_costs=self._settings.show_costs,
            debug=self._settings.debug,
        )
        await printer.print_spent()

    async def request_confirmation(self, question: str) -> uuid.UUID:
        warnings.warn(
            "request_confirmation is deprecated; use interrupt() in tools instead",
            DeprecationWarning,
            stacklevel=2,
        )
        if self._session_id is None:
            raise RuntimeError("Attribute _session_id in CLIChannel is None")

        confirmation_id = uuid.uuid4()
        await self._app.add_confirmation_message(
            question=question,
            session_id=self._session_id,
            confirmation_id=confirmation_id,
        )
        return confirmation_id

    async def _send_confirmation(self, entry: dict, session_id: uuid.UUID):
        confirmation_id = uuid.uuid4()
        await self._app.add_confirmation_message(
            question=entry.get("description", ""),
            session_id=session_id,
            confirmation_id=confirmation_id,
        )
        await self._syncer.set(
            f"{self.CONFIRMATION_PREFIX}:{session_id}:{confirmation_id}",
            {
                "session_id": str(session_id),
                "interrupt_id": entry.get("id"),
                "status": "pending",
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
        )

    async def _handle_confirmation_callback(self, session_id: uuid.UUID, confirmation_id: uuid.UUID, approved: bool):
        key = f"{self.CONFIRMATION_PREFIX}:{session_id}:{confirmation_id}"
        record = await self._syncer.get(key)
        if not record:
            return

        _session_id = uuid.UUID(record["session_id"])
        request_id = uuid.uuid4()
        agent = self._agent

        with self.set_current_request_id(request_id):
            printer = AgentMessagePrinter(
                app=self._app,
                session_id=_session_id,
                sessions_storage=self._sessions_storage,
                agent=agent,
                show_context_usage=self._settings.show_context_usage,
                show_costs=self._settings.show_costs,
                debug=self._settings.debug,
            )
            saver = AgentMessageSaver(
                sessions_storage=self._sessions_storage,
                session_id=_session_id,
            )

            async with (printer, saver):
                async for msg in agent.handle_confirmation(
                    session_id=_session_id,
                    decision=DecisionEnum.APPROVE if approved else DecisionEnum.REJECT,
                ):
                    await saver.register_new_message(msg)
                    await printer.register_new_message(msg)

        record["status"] = "resolved"
        await self._syncer.set(key, record)

    async def _create_session(self) -> uuid.UUID:
        session_id = uuid.uuid4()
        await self._sessions_storage.create_session(session_id=session_id)
        if self._user is not None:
            await self._users_storage.attach_session_to_user(
                user_id=self._user.id,
                session_id=session_id,
                channel_key=self._channel_key,
                channel_internal_id=self.CHANNEL_INTERNAL_ID,
            )
        return session_id
