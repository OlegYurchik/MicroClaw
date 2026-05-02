import facet
import uuid

from microclaw.agents import Agent
from microclaw.channels.base import BaseChannel
from microclaw.channels.utils import AgentMessageSaver
from microclaw.dto import AgentMessage, User
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.syncers import SyncerInterface
from microclaw.users_storages import UsersStorageInterface
from .loader import LoadingIndicator
from .printer import AgentMessagePrinter
from .settings import CLIChannelSettings


class CLIChannel(facet.AsyncioServiceMixin, BaseChannel):
    CHANNEL_INTERNAL_ID = "cli"
    HELP_MESSAGE = (
        "Available commands:\n"
        "  /help   - Show this help message\n"
        "  /quit   - Quit the session\n"
        "  /reset  - Reset the current session (start new conversation)"
    )

    def __init__(
            self,
            settings: CLIChannelSettings,
            agent: Agent,
            sessions_storage: SessionsStorageInterface,
            syncer: SyncerInterface,
            users_storage: UsersStorageInterface,
            resolver: "DependencyResolver",
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

        self._is_run = False
        self._user: User | None = None
        self._session_id: uuid.UUID | None = None
        self._saver: AgentMessageSaver | None = None
        self._printer: AgentMessagePrinter | None = None

    async def start(self):
        self.add_task(self.loop())

    async def loop(self):
        self._user = await self._get_or_create_user()
        self._session_id = await self._get_or_create_session()

        self._saver = AgentMessageSaver(
            sessions_storage=self._sessions_storage,
            session_id=self._session_id,
        )
        self._printer = AgentMessagePrinter(
            session_id=self._session_id,
            sessions_storage=self._sessions_storage,
            agent=self._agent,
            loader=LoadingIndicator() if self._settings.show_loader else None,
            show_context_usage=self._settings.show_context_usage,
            show_costs=self._settings.show_costs,
            debug=self._settings.debug,
        )
        
        self._printer.print(role="System", text="Type '/help' for available commands")
        self._is_run = True
        while self._is_run:
            input_prompt = self._printer.get_prompt(role="User")
            user_input = input(input_prompt)
            if not user_input:
                continue

            async with self._printer.catch_exception():
                await self.handle_user_input(user_input=user_input)

                if await self.is_context_went_across_threshold(session_id=self._session_id):
                    if await self.summarize_dialog_if_needed(session_id=self._session_id):
                        self._printer.print(role="System", text="Dialog summarized")
                    else:
                        self._printer.print(
                            role="System",
                            text="Context window threshold exceeded",
                        )
        self._printer.print(text="========== Conversation is end ==========")

    async def handle_user_input(self, user_input: str):
        if user_input.startswith("/"):
            await self.handle_command(command=user_input[1:])
            return

        user_message = AgentMessage(role="user", text=user_input)
        message_generator = self._sessions_storage.get_messages(session_id=self._session_id)
        messages = [message async for message in message_generator]
        messages.append(user_message)

        agent = await self.get_agent_for_user(self._user)
        agent = agent or self._agent

        async with (self._printer, self._saver):
            await self._saver.register_new_message(user_message)

            async for new_message in agent.ask(messages=messages, channel=self, stream=True):
                await self._saver.register_new_message(new_message)
                await self._printer.register_new_message(new_message)
                if self._printer.is_finished:
                    self._is_run = False
                    return

    async def handle_command(self, command: str):
        match command:
            case "quit":
                self._is_run = False
            case "reset":
                self._session_id = await self._get_or_create_session()
                self._saver = AgentMessageSaver(
                    sessions_storage=self._sessions_storage,
                    session_id=self._session_id,
                )
                self._printer = AgentMessagePrinter(
                    session_id=self._session_id,
                    sessions_storage=self._sessions_storage,
                    agent=self._agent,
                    loader=LoadingIndicator() if self._settings.show_loader else None,
                    show_context_usage=self._settings.show_context_usage,
                    show_costs=self._settings.show_costs,
                    debug=self._settings.debug,
                )
            case "help":
                for help_line in self.HELP_MESSAGE.split("\n"):
                    self._printer.print(role="System", text=help_line)
            case _:
                self._printer.print(role="System", text="Unknown command.", )
                for help_line in self.HELP_MESSAGE.split("\n"):
                    self._printer.print(role="System", text=help_line)

    async def _get_or_create_user(self) -> User:
        user = await self._users_storage.get_user_by_channel(
            channel_key=self._channel_key,
            channel_internal_id=self.CHANNEL_INTERNAL_ID,
        )
        if user:
            return user

        user = await self._users_storage.create_user()
        return user

    async def start_conversation(
            self,
            channel_internal_id: str,
            session_id: uuid.UUID | None = None,
            messages: list[AgentMessage] | None = None,
            agent: Agent | None = None,
    ):
        user = await self._users_storage.get_user_by_channel(
            channel_key=self._channel_key,
            channel_internal_id=self.CHANNEL_INTERNAL_ID,
        )
        if user is None:
            raise RuntimeError(f"User not found for channel_internal_id={channel_internal_id}")

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
            session_id=session_id,
            sessions_storage=self._sessions_storage,
            agent=agent,
            loader=LoadingIndicator() if self._settings.show_loader else None,
            show_context_usage=self._settings.show_context_usage,
            show_costs=self._settings.show_costs,
            debug=self._settings.debug,
        )

        async with (printer.catch_exception(), saver, printer):
            async for new_message in agent.ask(messages=all_messages, channel=self, stream=True):
                await saver.register_new_message(new_message)
                await printer.register_new_message(new_message)

    async def _get_or_create_session(self) -> uuid.UUID:
        session_id = await self._users_storage.get_actual_session(
            user_id=self._user.id,
            channel_key=self._channel_key,
            channel_internal_id=self.CHANNEL_INTERNAL_ID,
        )
        if session_id is not None:
            return session_id

        session_id = uuid.uuid4()
        await self._sessions_storage.create_session(session_id=session_id)
        await self._users_storage.attach_session_to_user(
            user_id=self._user.id,
            session_id=session_id,
            channel_key=self._channel_key,
            channel_internal_id=self.CHANNEL_INTERNAL_ID,
        )
        return session_id
