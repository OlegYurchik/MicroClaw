import uuid
from typing import AsyncGenerator

from microclaw.dto import AgentMessage, Spending
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from .settings import MemorySessionsStorageSettings


class MemorySessionsStorage(SessionsStorageInterface):
    def __init__(self, settings: MemorySessionsStorageSettings):
        self._messages: dict[uuid.UUID, list[AgentMessage]] = {}
        self._spendings: dict[uuid.UUID, Spending] = {}
        self._context: dict[uuid.UUID, int] = {}

    async def create_session(self, session_id: uuid.UUID | None = None) -> uuid.UUID:
        if session_id is None:
            session_id = uuid.uuid4()

        if session_id not in self._messages:
            self._messages[session_id] = []
        if session_id not in self._context:
            self._context[session_id] = 0

        return session_id

    async def add_message(self, session_id: uuid.UUID, message: AgentMessage):
        self._messages[session_id].append(message)
        if message.spending is None:
            return

        if message.is_summary:
            self._context[session_id] = message.spending.output_tokens
        elif session_id not in self._context:
            self._context[session_id] = message.spending.get_total_tokens()
        else:
            self._context[session_id] += message.spending.get_total_tokens()

        if session_id in self._spendings:
            self._spendings[session_id] += message.spending
        else:
            self._spendings[session_id] = message.spending

    async def get_messages(
            self,
            session_id: uuid.UUID,
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

    async def get_spending(self, session_id: uuid.UUID) -> Spending:
        return self._spendings.get(session_id, Spending())

    async def get_context_size(self, session_id: uuid.UUID) -> int:
        return self._context.get(session_id, 0)
