from collections.abc import AsyncGenerator

from .filters import MessageFilter, SessionFilter
from pydantic_filters import BaseSort
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.dto import AgentMessage, Session
from microclaw.sessions_storages.dto import (
    MessageCreate,
    MessageUpdate,
    SessionCreate,
    SessionUpdate,
)


class SessionsStorageInterface:
    # Sessions
    async def get_session(
        self,
        filter_: SessionFilter,
        sort: BaseSort | None = None,
    ) -> Session | None:
        raise NotImplementedError

    async def get_sessions(
        self,
        filter_: SessionFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[Session]:
        raise NotImplementedError

    async def create_session(
        self,
        data: SessionCreate,
    ) -> Session:
        raise NotImplementedError

    async def update_sessions(
        self,
        filter_: SessionFilter | None = None,
        *, data: SessionUpdate,
    ) -> AsyncGenerator[Session]:
        raise NotImplementedError

    async def update_session(
        self,
        filter_: SessionFilter,
        *, data: SessionUpdate,
    ) -> Session | None:
        async for session in self.update_sessions(filter_=filter_, data=data):
            return session
        return None

    async def delete_session(self, filter_: SessionFilter) -> None:
        raise NotImplementedError

    async def delete_sessions(self, filter_: SessionFilter | None = None) -> None:
        raise NotImplementedError

    async def get_context_size(self, filter_: SessionFilter) -> int:
        session = await self.get_session(filter_=filter_)
        return session.context_size if session else 0

    # Messages
    async def get_message(
        self,
        filter_: MessageFilter,
        sort: BaseSort | None = None,
    ) -> AgentMessage | None:
        raise NotImplementedError

    async def get_messages(
        self,
        filter_: MessageFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[AgentMessage]:
        raise NotImplementedError

    async def create_message(
        self,
        data: MessageCreate,
    ) -> AgentMessage:
        raise NotImplementedError

    async def update_messages(
        self,
        filter_: MessageFilter | None = None,
        *, data: MessageUpdate,
    ) -> AsyncGenerator[AgentMessage]:
        raise NotImplementedError

    async def update_message(
        self,
        filter_: MessageFilter,
        *, data: MessageUpdate,
    ) -> AgentMessage | None:
        async for message in self.update_messages(filter_=filter_, data=data):
            return message
        return None

    async def delete_message(self, filter_: MessageFilter) -> None:
        raise NotImplementedError

    async def delete_messages(self, filter_: MessageFilter | None = None) -> None:
        raise NotImplementedError
