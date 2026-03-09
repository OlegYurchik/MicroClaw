from collections import defaultdict
from typing import AsyncGenerator

from microclaw.dto import AgentMessage, Spending
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from .settings import MemorySessionsStorageSettings


class MemorySessionsStorage(SessionsStorageInterface):
    def __init__(self, settings: MemorySessionsStorageSettings):
        self._messages: dict[str, list[AgentMessage]] = defaultdict(list)
        self._total_spendings: dict[str, Spending] = {}

    async def add_message(self, session_id: str, message: AgentMessage):
        self._messages[session_id].append(message)
        if message.spending is None:
            return

        spending = self._total_spendings.get(session_id)
        if spending is None:
            self._total_spendings[session_id] = message.spending
        elif message.spending.is_summary:
            new_spending = message.spending.model_copy()
            new_spending.cost += spending.cost
            self._total_spendings[session_id] = new_spending
        else:
            self._total_spendings[session_id] += message.spending

    async def get_messages(
            self,
            session_id: str,
            last: int | None = None,
            from_last_summarization: bool = True,
    ) -> AsyncGenerator[AgentMessage]:
        messages = self._messages[session_id]
        if last is None:
            last = len(messages)
        messages = messages[-last:]

        if from_last_summarization:
            index = 0
            for i, message in enumerate(messages):
                if message.is_summary:
                    index = i
        else:
            index = 0
        
        for message in messages[index:]:
            yield message

    async def get_spending(self, session_id: str) -> Spending:
        return self._total_spendings.get(session_id, Spending())