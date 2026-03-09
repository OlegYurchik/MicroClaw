import facet
import uuid

from microclaw.agents import Agent
from microclaw.channels.interfaces import ChannelInterface
from microclaw.dto import AgentMessage
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from .loader import LoadingIndicator
from .settings import CLIChannelSettings


class CLIChannel(facet.AsyncioServiceMixin, ChannelInterface):
    END_PHRASE = "NO_REPLY"
    LJUST_COUNT = 6
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
        self._session_id = f"cli:{uuid.uuid4()}"
        self._is_run = False
        self._loading_indicator = LoadingIndicator() if settings.show_loader else None

    async def start(self):
        self.add_task(self.loop())

    async def loop(self):
        self._print_content(
            role="System",
            content="Type '/help' for available commands",
        )
        self._is_run = True
        while self._is_run:
            user_role = "User".ljust(self.LJUST_COUNT)
            user_input = input(f"[{user_role}] > ")
            if not user_input:
                continue
   
            messages = await self.handle_user_input(user_input=user_input)
            for message in messages:
                await self._sessions_storage.add_message(
                    session_id=self._session_id,
                    message=message,
                )
            spending = await self._sessions_storage.get_spending(session_id=self._session_id)
            spents_content = []
            if self._settings.show_costs:
                spents_content.append(f"{spending.cost:.4f}{spending.currency}")
            if self._settings.show_context_usage:
                context_window_size = self._agent.get_model_context_window_size()
                if context_window_size is not None:
                    context_load = spending.get_total_tokens() / context_window_size
                    spents_content.append(f"{context_load:.2f}% context")
            if spents_content:
                self._print_content(content=" · ".join(spents_content), role="Spents")

            if await self.is_context_went_across_threshold():
                if await self.summarize_dialog_if_needed():
                    self._print_content(content="Dialog summarized", role="System")
                else:
                    self._print_content(
                        content="Context window threshold exceeded",
                        role="System",
                    )
        self._print_content(content="========== Conversation is end ==========")

    async def handle_user_input(self, user_input: str) -> list[AgentMessage]:
        match user_input:
            case "/quit":
                self._is_run = False
                return []
            case "/reset":
                self._session_id = f"cli:{uuid.uuid4()}"
                return []
            case "/help":
                for help_line in self.HELP_MESSAGE.split("\n"):
                    self._print_content(content=help_line, role="System")
                return []
        if user_input.startswith("/"):
            self._print_content(content="Unknown command.", role="System")
            for help_line in self.HELP_MESSAGE.split("\n"):
                self._print_content(content=help_line, role="System")

        await self._sessions_storage.add_message(
            session_id=self._session_id,
            message=AgentMessage(role="user", content=user_input),
        )
        message_generator = self._sessions_storage.get_messages(session_id=self._session_id)
        messages = [message async for message in message_generator]

        messages_queue = []
        last_chunked_message_id = None
        buffer = ""
        first_printed = False
        if self._loading_indicator:
            self._loading_indicator.start()
        async for new_message in self._agent.ask(messages=messages):
            if self._loading_indicator:
                self._loading_indicator.stop()
            is_new_chunk = (
                new_message.chunked_message_id is None or
                new_message.chunked_message_id != last_chunked_message_id
            )

            if is_new_chunk:
                messages_queue.append(new_message)
                content_to_print = new_message.content
            else:
                messages_queue[-1].content += new_message.content
                content_to_print = buffer + new_message.content

            if self._is_ending_message(content_to_print):
                self._is_run = False
                return messages_queue

            if new_message.role != "assistant" or not new_message.content:
                last_chunked_message_id = new_message.chunked_message_id
                if self._loading_indicator:
                    self._loading_indicator.start()
                continue

            buffer = self._maybe_buffer_ending(new_message.content, is_new_chunk, buffer)
            if not buffer:
                self._print_content(
                    content=content_to_print,
                    role="AI" if is_new_chunk else None,
                    need_pre_new_line=not first_printed,
                    need_post_new_line=False,
                )
                first_printed = True

            last_chunked_message_id = new_message.chunked_message_id
            if self._loading_indicator:
                self._loading_indicator.start()
        if self._loading_indicator:
            self._loading_indicator.stop()
        self._print_content(content="")

        return messages_queue

        

    @classmethod
    def _is_ending_message(cls, content: str) -> bool:
        return content.strip().upper() == cls.END_PHRASE

    def _maybe_buffer_ending(self, content: str, is_new_chunk: bool, current_buffer: str = "") -> str:
        if self.END_PHRASE.startswith(content.strip().upper()):
            return current_buffer + content
        return ""

    def _print_content(
            self,
            content: str,
            role: str | None = None,
            need_pre_new_line: bool = False,
            need_post_new_line: bool = True,
    ) -> None:
        if need_pre_new_line:
            print()
        if role is not None:
            role_formatted = role[:self.LJUST_COUNT].ljust(self.LJUST_COUNT)
            print(f"[{role_formatted}] > ", end="", flush=True)
        print(content, end="", flush=True)
        if need_post_new_line:
            print()

    