import uuid
from typing import AsyncGenerator

import facet

from pydantic_filters import BaseSort
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.dto import AgentMessage, Spending
from .filters import SessionFilter, MessageFilter


class SessionsStorageInterface(facet.AsyncioServiceMixin):
    async def create_session(
        self,
        session_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        raise NotImplementedError

    async def get_sessions(
        self,
        filter: SessionFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[uuid.UUID]:
        raise NotImplementedError

    async def add_message(self, session_id: uuid.UUID, message: AgentMessage):
        raise NotImplementedError

    async def get_messages(
        self,
        filter: MessageFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
        from_last_summarization: bool = True,
    ) -> AsyncGenerator[AgentMessage]:
        raise NotImplementedError

    async def get_spending(self, session_id: uuid.UUID) -> Spending:
        raise NotImplementedError

    async def get_context_size(self, session_id: uuid.UUID) -> int:
        raise NotImplementedError
