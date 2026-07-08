import json
import uuid
from typing import Sequence

from microclaw.agents import Agent
from microclaw.channels.base import BaseChannel
from microclaw.channels.utils import AgentMessageSaver
from microclaw.dto import AgentMessage, DecisionEnum, User
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.sessions_storages.filters import MessageFilter
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
        await self._generate_and_send_answer(
            agent=agent,
            session_id=session_id,
            new_messages=new_messages,
        )

    async def handle_user_message(self, text: str, agent: Agent | None = None) -> None:
        if self._session_id is None:
            self._session_id = await self._create_session()

        user_message = AgentMessage(role="user", text=text)
        await self._generate_and_send_answer(
            session_id=self._session_id,
            agent=agent,
            new_messages=[user_message],
        )

    async def _generate_and_send_answer(
        self,
        session_id: uuid.UUID,
        agent: Agent | None = None,
        new_messages: Sequence[AgentMessage] = (),
    ):
        agent = agent or await self.get_agent_for_user(self._user) or self._agent

        for message in new_messages:
            await self._sessions_storage.add_message(
                session_id=session_id,
                message=message,
            )

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

        message_generator = self._sessions_storage.get_messages(
            filter=MessageFilter(session_id=session_id)
        )
        history = [_message async for _message in message_generator]

        with (
            self.set_current_channel(),
            self.set_current_session_id(session_id),
        ):
            await printer.show_thinking()

            async with printer, saver:
                new_message_generator = (
                    agent.resume_after_confirmation(
                        session_id=session_id,
                        decision=DecisionEnum.REJECT,
                        new_messages=new_messages,
                        channel=self,
                    )
                    if await agent.has_pending_interrupt(session_id=session_id)
                    else agent.ask(messages=history, channel=self, stream=True)
                )
                async for new_message in new_message_generator:
                    if new_message.role == "request_confirmation":
                        entries = json.loads(new_message.text)
                        for entry in entries:
                            await self._send_confirmation(entry, session_id)
                        continue
                    await saver.register_new_message(new_message)
                    await printer.register_new_message(new_message)

            async with printer:
                if (
                    agent.is_summarization_enabled()
                    and await self.is_context_went_across_threshold(
                        agent=agent,
                        session_id=session_id,
                    )
                ):
                    await self._app.add_message(
                        role=RoleEnum.SYSTEM, text="[dim]Summarizing...[/dim]"
                    )
                    await self.summarize_dialog_if_needed(
                        agent=agent, session_id=session_id
                    )
                    await self._app.update_message(
                        role=RoleEnum.SYSTEM, text="Dialog summarized"
                    )

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

    async def _send_confirmation(self, entry: dict, session_id: uuid.UUID):
        await self._app.add_confirmation_message(
            question=entry.get("description", ""),
            session_id=session_id,
        )

    async def _handle_confirmation_callback(
        self, session_id: uuid.UUID, approved: bool
    ):
        request_id = uuid.uuid4()
        agent = self._agent

        with self.set_current_request_id(request_id):
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

            async with printer, saver:
                async for msg in agent.resume_after_confirmation(
                    session_id=session_id,
                    decision=DecisionEnum.APPROVE if approved else DecisionEnum.REJECT,
                    channel=self,
                ):
                    await saver.register_new_message(msg)
                    await printer.register_new_message(msg)

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
