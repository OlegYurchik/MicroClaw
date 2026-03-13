import facet
import uuid

from microclaw.agents import Agent
from microclaw.channels.interfaces import ChannelInterface
from microclaw.channels.utils import AgentMessageSaver
from microclaw.dto import AgentMessage
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from .loader import LoadingIndicator
from .printer import AgentMessagePrinter
from .settings import CLIChannelSettings


class CLIChannel(facet.AsyncioServiceMixin, ChannelInterface):
    """Console interface channel for communication.

    Communication happens through a console interface. Respond with plain text only.
    Do not create tables or diagrams wider than 40 characters or taller than 40 lines.
    Remember that all characters are monospace.
    """

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
            channel_key: str = "default",
    ):
        super().__init__(
            settings=settings,
            agent=agent,
            sessions_storage=sessions_storage,
            channel_key=channel_key,
        )

        self._is_run = False
        self._session_id = uuid.uuid4()
        self._saver = AgentMessageSaver(
            sessions_storage=sessions_storage,
            session_id=self._session_id,
        )
        self._printer = AgentMessagePrinter(
            session_id=self._session_id,
            sessions_storage=sessions_storage,
            agent=agent,
            loader=LoadingIndicator() if self._settings.show_loader else None,
            show_context_usage=self._settings.show_context_usage,
            show_costs=self._settings.show_costs,
            debug=self._settings.debug,
        )

    async def start(self):
        self.add_task(self.loop())

    async def loop(self):
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

        async with (self._saver, self._printer):
            await self._saver.register_new_message(user_message)

            async for new_message in self._agent.ask(messages=messages, channel=self):
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
                self._session_id = uuid.uuid4()
            case "help":
                for help_line in self.HELP_MESSAGE.split("\n"):
                    self._printer.print(role="System", text=help_line)
            case _:
                self._printer.print(role="System", text="Unknown command.", )
                for help_line in self.HELP_MESSAGE.split("\n"):
                    self._printer.print(role="System", text=help_line)
