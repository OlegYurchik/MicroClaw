import uuid
from datetime import date
from typing import AsyncGenerator

from pydantic_filters import BasePagination

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
        date_filter: date | None = None,
    ) -> AsyncGenerator[uuid.UUID]:
        filter_ = None
        if date_filter is not None:
            filter_ = SessionFilter(created_at=date_filter)
        async for item in self.get_items(filter_=filter_):
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
        session_id: uuid.UUID,
        last: int | None = None,
    ) -> AsyncGenerator[AgentMessage]:
        if last is not None:
            pagination = BasePagination(limit=last, offset=0)
            async for item in self.get_items(
                filter_=MessageFilter(session_id=session_id),
                pagination=pagination,
            ):
                yield item
        else:
            async for item in self.get_items(filter_=MessageFilter(session_id=session_id)):
                yield item
