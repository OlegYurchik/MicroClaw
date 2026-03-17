import uuid
from contextlib import asynccontextmanager

from microclaw.agents import Agent
from microclaw.channels.utils import AgentMessageHandler
from microclaw.dto import AgentMessage
from microclaw.sessions_storages import SessionsStorageInterface
from .loader import LoadingIndicator


class AgentMessagePrinter(AgentMessageHandler):
    LJUST_COUNT = 6
    FINISH_MESSAGE = "NO_REPLY"

    def __init__(
            self,
            session_id: uuid.UUID,
            sessions_storage: SessionsStorageInterface,
            agent: Agent,
            loader: LoadingIndicator | None = None,
            show_context_usage: bool = False,
            show_costs: bool = False,
            debug: bool = False,
    ):
        super().__init__()
        self._session_id = session_id
        self._sessions_storage = sessions_storage
        self._agent = agent
        self._loader = loader
        self._show_context_usage = show_context_usage
        self._show_costs = show_costs
        self._debug = debug

        self._buffer = ""
        self._is_finished = False

    async def __aenter__(self):
        await super().__aenter__()
        self._start_loader()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._stop_loader()
        await self.print_spent()
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def handle_new_message(self, new_message: AgentMessage):
        if new_message.role != "assistant" or not new_message.text:
            return

        self._stop_loader()
        if self.is_new_message_chunk:
            if self._buffer:
                print(self._buffer, flush=True)
            prompt = self.get_prompt(role="AI")
            print(prompt, end="", flush=True)
            self._buffer = new_message.text
        else:
            self._buffer += new_message.text

        if self._buffer == self.FINISH_MESSAGE:
            self._is_finished = True
            return
        if self._like_a_finish_message():
            return

        print(self._buffer, end="", flush=True)
        self._buffer = ""
        self._start_loader()

    def _like_a_finish_message(self) -> bool:
        return self.FINISH_MESSAGE.startswith(self._buffer)

    def _start_loader(self):
        if self._loader is not None:
            self._loader.start()

    def _stop_loader(self):
        if self._loader is not None:
            self._loader.stop()

    @property
    def is_finished(self) -> bool:
        return self._is_finished

    async def print_spent(self):
        print()
        spent_texts = []
        if self._show_context_usage:
            actual_context_size = await self._sessions_storage.get_context_size(
                session_id=self._session_id,
            )
            model_context_size = self._agent.get_model_context_window_size()
            if model_context_size:
                context_usage = actual_context_size * 100 / model_context_size
                spent_texts.append(f"{context_usage:.2f}% context")
        if self._show_costs:
            spending = await self._sessions_storage.get_spending(session_id=self._session_id)
            spent_texts.append(f"{spending.cost:.4f} {spending.currency}")
        self.print(role="Spents", text=" · ".join(spent_texts))

    @classmethod
    def print(cls, text: str, role: str | None = None):
        """External method for printing messages."""

        if role is not None:
            prompt = cls.get_prompt(role=role)
            text = prompt + text
        print(text)

    @classmethod
    def get_prompt(cls, role: str) -> str:
        role_formatted = role[:cls.LJUST_COUNT].ljust(cls.LJUST_COUNT)
        return f"[{role_formatted}] > "

    @asynccontextmanager
    async def catch_exception(self):
        try:
            yield
        except Exception as exception:
            if self._debug:
                self.print(role="System", text=f"Got exception: {exception}")
            else:
                self.print(
                    role="System",
                    text="Internal error, please contact agent administrator",
                )