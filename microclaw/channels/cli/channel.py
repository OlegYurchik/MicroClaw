import uuid

from microclaw.agents import Agent
from microclaw.channels.base import BaseChannel
from microclaw.channels.utils import AgentMessageSaver
from microclaw.dto import AgentMessage, User
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
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
        self._session_id = await self._create_session()

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

        message_generator = self._sessions_storage.get_messages(session_id=session_id)
        messages = [_message async for _message in message_generator]

        with self.set_current_channel():
            async with (printer, saver):
                async for new_message in agent.ask(messages=messages, channel=self, stream=True):
                    await saver.register_new_message(new_message)
                    await printer.register_new_message(new_message)

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
        confirmation_id = uuid.uuid4()
        self._app.show_confirmation_modal(question, confirmation_id)
        return confirmation_id

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
