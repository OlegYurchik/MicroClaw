import uuid

from microclaw.agents import Agent
from microclaw.channels.utils import AgentMessageCollector
from microclaw.dto import AgentMessage
from microclaw.sessions_storages import SessionsStorageInterface
from .ui import RoleEnum


class AgentMessagePrinter(AgentMessageCollector):
    def __init__(
            self,
            app,
            session_id: uuid.UUID,
            sessions_storage: SessionsStorageInterface,
            agent: Agent,
            show_context_usage: bool = False,
            show_costs: bool = False,
            debug: bool = False,
    ):
        super().__init__()
        self._app = app
        self._session_id = session_id
        self._sessions_storage = sessions_storage
        self._agent = agent
        self._show_context_usage = show_context_usage
        self._show_costs = show_costs
        self._debug = debug

        self._text = ""

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        await self.print_spent()
        if exc_type is not None:
            if self._debug:
                text = f"Got exception: {exc_val}"
            else:
                text = "Internal error, please contact agent administrator"
            await self._create_message_widget(role=RoleEnum.SYSTEM, text=text)
        await super().__aexit__(exc_type, exc_val, exc_tb)
        return True

    async def handle_new_message(self, new_message: AgentMessage):
        if new_message.role != "assistant" or not new_message.text:
            return

        if self.is_new_message_chunk:
            self._text = new_message.text
            await self._create_message_widget(role=RoleEnum.AI, text=self._text)
        else:
            self._text += new_message.text
            await self._update_message_widget(role=RoleEnum.AI, text=self._text)

    async def _create_message_widget(self, role: RoleEnum, text: str | None = None):
        await self._app.add_message(role=role, text=text)

    async def _update_message_widget(
            self,
            role: RoleEnum,
            text: str | None = None,
    ):
        await self._app.update_message(role=role, text=text)

    async def print_spent(self):
        context_usage = None
        cost = None
        currency = "$"

        if self._show_context_usage:
            actual_context_size = await self._sessions_storage.get_context_size(
                session_id=self._session_id,
            )
            model_context_size = self._agent.get_model_context_window_size()
            if model_context_size:
                context_usage = actual_context_size * 100 / model_context_size

        if self._show_costs:
            spending = await self._sessions_storage.get_spending(session_id=self._session_id)
            cost = spending.cost
            currency = spending.currency

        self._app.update_stats(
            context_usage=context_usage,
            cost=cost,
            currency=currency,
        )
