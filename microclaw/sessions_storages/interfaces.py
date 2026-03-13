import uuid
from typing import AsyncGenerator

import facet

from microclaw.dto import AgentMessage, Spending


class SessionsStorageInterface(facet.AsyncioServiceMixin):
    async def add_message(self, session_id: uuid.UUID, message: AgentMessage):
        raise NotImplementedError

    async def get_messages(
            self,
            session_id: uuid.UUID,
            last: int | None = None,
            from_last_summarization: bool = True,
    ) -> AsyncGenerator[AgentMessage]:
        raise NotImplementedError

    async def get_spending(self, session_id: uuid.UUID) -> Spending:
        raise NotImplementedError

    async def get_context_size(self, session_id: uuid.UUID) -> int:
        raise NotImplementedError
