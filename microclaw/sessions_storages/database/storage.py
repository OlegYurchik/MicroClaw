from collections.abc import AsyncGenerator
import datetime
import json

from .dto import SessionData
from .repository import MessagesRepository, SessionsRepository
from .settings import DatabaseSessionsStorageSettings
from .tables import MessageTable, SessionTable
import facet
from metaorm import BaseTable, NotFoundError, RepositoriesContainer
from pydantic_filters import BaseSort
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.dto import AgentMessage, AgentMessageRoleEnum, Session
from microclaw.sessions_storages.dto import (
    MessageCreate,
    MessageUpdate,
    SessionCreate,
    SessionUpdate,
)
from microclaw.sessions_storages.filters import MessageFilter, SessionFilter
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.utils import utcnow


def _ensure_aware(dt: datetime.datetime | None) -> datetime.datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt


class DatabaseSessionsStorage(SessionsStorageInterface, facet.AsyncioServiceMixin):
    def __init__(self, settings: DatabaseSessionsStorageSettings):
        self._settings = settings
        self._container = RepositoriesContainer(settings=settings)
        self._sessions_repository = self._container.get_repository(SessionsRepository)
        self._messages_repository = self._container.get_repository(MessagesRepository)

    async def start(self):
        async with self._container.engine.begin() as conn:
            await conn.run_sync(BaseTable.metadata.create_all)

    async def stop(self):
        await self._container.engine.dispose()

    async def create_session(
        self,
        data: SessionCreate,
    ) -> Session:
        session_id = data.id
        channel_key = data.channel_key
        channel_internal_id = data.channel_internal_id

        session_data = SessionData(
            id=session_id,
            created_at=utcnow(),
            updated_at=utcnow(),
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
            context_size=0,
            spending=None,
        )
        result = await self._sessions_repository.create_item(session_data)
        return Session(
            id=result.id,
            channel_key=result.channel_key,
            channel_internal_id=result.channel_internal_id,
            context_size=result.context_size,
            spending=result.spending,
            created_at=_ensure_aware(result.created_at),
            updated_at=_ensure_aware(result.updated_at),
        )

    async def get_session(
        self,
        filter_: SessionFilter,
        sort: BaseSort | None = None,
    ) -> Session | None:
        session = await self._sessions_repository.get_item(
            filter_=filter_, sort=sort
        )
        if session is None:
            return None
        return Session(
            id=session.id,
            channel_key=session.channel_key,
            channel_internal_id=session.channel_internal_id,
            context_size=session.context_size,
            spending=session.spending,
            created_at=_ensure_aware(session.created_at),
            updated_at=_ensure_aware(session.updated_at),
        )

    async def get_sessions(
        self,
        filter_: SessionFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[Session]:
        async for session in self._sessions_repository.get_items(
            filter_=filter_, pagination=pagination, sort=sort
        ):
            yield Session(
                id=session.id,
                channel_key=session.channel_key,
                channel_internal_id=session.channel_internal_id,
                context_size=session.context_size,
                spending=session.spending,
                created_at=_ensure_aware(session.created_at),
                updated_at=_ensure_aware(session.updated_at),
            )

    async def update_sessions(
        self,
        filter_: SessionFilter | None = None,
        *, data: SessionUpdate,
    ) -> AsyncGenerator[Session]:
        values = {}
        if data.context_size is not None:
            values["context_size"] = data.context_size
        if data.spending is not None:
            values["spending"] = SessionTable.serialize_spending(data.spending)
        values["updated_at"] = utcnow()
        async for item in self._sessions_repository.update_items(filter_=filter_, **values):
            yield Session(
                id=item.id,
                channel_key=item.channel_key,
                channel_internal_id=item.channel_internal_id,
                context_size=item.context_size,
                spending=item.spending,
                created_at=_ensure_aware(item.created_at),
                updated_at=_ensure_aware(item.updated_at),
            )

    async def delete_session(self, filter_: SessionFilter) -> None:
        await self.delete_sessions(filter_=filter_)

    async def delete_sessions(self, filter_: SessionFilter | None = None) -> None:
        async with self._container.transaction():
            session_ids = []
            async for session in self._sessions_repository.get_items(filter_=filter_):
                session_ids.append(session.id)
            if session_ids:
                await self._messages_repository.delete_items(
                    filter_=MessageFilter(session_id=set(session_ids))
                )
            await self._sessions_repository.delete_items(filter_=filter_)

    async def create_message(self, data: MessageCreate) -> AgentMessage:
        async with self._container.transaction():
            session = await self._sessions_repository.get_item(
                filter_=SessionFilter(id={data.session_id})
            )
            if session is None:
                raise NotFoundError(f"Session {data.session_id} not found")

            message_table = MessageTable.from_item(data.message, session_id=data.session_id)
            message = await self._messages_repository.create_item(message_table)

            context_size = session.context_size
            if data.message.spending:
                if data.message.role == AgentMessageRoleEnum.SUMMARY:
                    context_size = data.message.spending.output_tokens
                elif data.message.context_tokens is not None:
                    context_size = data.message.context_tokens
                else:
                    context_size = (
                        data.message.spending.input_tokens + data.message.spending.output_tokens
                    )

            spending_str = None
            if data.message.spending:
                if session.spending is None:
                    spending_str = json.dumps(data.message.spending.model_dump())
                else:
                    spending_str = json.dumps((session.spending + data.message.spending).model_dump())

            async for _ in self._sessions_repository.update_items(
                filter_=SessionFilter(id={data.session_id}),
                context_size=context_size,
                spending=spending_str,
                updated_at=utcnow(),
            ):
                pass

            return message

    async def get_message(
        self,
        filter_: MessageFilter,
        sort: BaseSort | None = None,
    ) -> AgentMessage | None:
        message = await self._messages_repository.get_item(filter_=filter_, sort=sort)
        if message is None:
            return None
        return message

    async def get_messages(
        self,
        filter_: MessageFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[AgentMessage]:
        async for message in self._messages_repository.get_items(
            filter_=filter_, pagination=pagination, sort=sort
        ):
            yield message

    async def update_messages(
        self,
        filter_: MessageFilter | None = None,
        *, data: MessageUpdate,
    ) -> AsyncGenerator[AgentMessage]:
        values = {}
        if data.role is not None:
            values["role"] = data.role
        if data.text is not None:
            values["text"] = data.text
        async for item in self._messages_repository.update_items(filter_=filter_, **values):
            yield item

    async def delete_message(self, filter_: MessageFilter) -> None:
        await self._messages_repository.delete_items(filter_=filter_)

    async def delete_messages(self, filter_: MessageFilter | None = None) -> None:
        await self._messages_repository.delete_items(filter_=filter_)
