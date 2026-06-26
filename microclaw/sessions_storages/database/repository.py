import uuid
from datetime import date
from typing import AsyncGenerator

from pydantic_filters import BaseSort
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.dto import AgentMessage
from microclaw.utils.database.base import BaseRepository
from microclaw.utils.database.tables import BaseTable

from .dto import SessionData
from .filters import MessageFilter, SessionFilter
from .tables import MessageTable, SessionTable


class SessionsRepository(BaseRepository[SessionData, SessionFilter]):
    def get_db_table(self) -> type[BaseTable]:
        return SessionTable

    async def get_session(self, session_id: uuid.UUID) -> SessionData | None:
        async for item in self.get_items(filter_=SessionFilter(id=session_id)):
            return item
        return None

    async def get_sessions(
        self,
        date_filter: SessionFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[uuid.UUID]:
        async for item in self.get_items(filter_=date_filter, pagination=pagination, sort=sort):
            yield item.id

    async def create_session(self, session_id: uuid.UUID) -> SessionData:
        session_data = SessionData(
            id=session_id,
            created_at=None,
            updated_at=None,
        )
        return await self.create_item(session_data)

    async def update_session(
        self,
        session_id: uuid.UUID,
        context_size: int,
        spending: dict | None = None,
    ) -> SessionData | None:
        values = {"context_size": context_size}
        if spending is not None:
            values["spending"] = spending
        async for item in self.update_items(
            filter_=SessionFilter(id=session_id),
            **values,
        ):
            return item


class MessagesRepository(BaseRepository[AgentMessage, MessageFilter]):
    def get_db_table(self) -> type[BaseTable]:
        return MessageTable

    async def add_message(self, session_id: uuid.UUID, message: AgentMessage) -> AgentMessage:
        message_table = MessageTable.from_item(message, session_id)
        return await self.create_item(message_table)

    async def get_messages(
        self,
        filter_: MessageFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[AgentMessage]:
        async for item in self.get_items(
            filter_=filter_,
            pagination=pagination,
            sort=sort,
        ):
            yield item
