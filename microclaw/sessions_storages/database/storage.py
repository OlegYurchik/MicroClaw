from collections.abc import AsyncGenerator
import uuid

from .repository import MessagesRepository, SessionsRepository
from .settings import DatabaseSessionsStorageSettings
from .tables import SessionTable
from pydantic_filters import BaseSort
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.dto import AgentMessage, SessionMetadata, Spending
from microclaw.sessions_storages.filters import MessageFilter, SessionFilter
from microclaw.sessions_storages.interfaces import SessionsStorageInterface


class DatabaseSessionsStorage(SessionsStorageInterface):
    def __init__(self, settings: DatabaseSessionsStorageSettings):
        self._settings = settings
        self._sessions_repository = SessionsRepository(settings=settings)
        self._messages_repository = MessagesRepository(settings=settings)

    async def start(self):
        async with self._sessions_repository._engine.begin() as conn:
            await conn.run_sync(SessionTable.metadata.create_all)

    async def stop(self):
        pass

    async def create_session(self, session_id: uuid.UUID | None = None) -> uuid.UUID:
        if session_id is None:
            session_id = uuid.uuid4()

        async with self._sessions_repository.transaction():
            session = await self._sessions_repository.get_session(session_id)
            if session is None:
                session = await self._sessions_repository.create_session(session_id)

        return session_id

    async def add_message(self, session_id: uuid.UUID, message: AgentMessage):
        async with self._sessions_repository.transaction():
            session = await self._sessions_repository.get_session(session_id)
            if session is None:
                session = await self._sessions_repository.create_session(session_id)

            await self._messages_repository.add_message(session_id, message)

            context_size = session.context
            if message.spending:
                if message.role == "summary":
                    context_size = message.spending.output_tokens
                elif message.context_tokens is not None:
                    context_size = message.context_tokens
                else:
                    context_size = (
                        message.spending.input_tokens + message.spending.output_tokens
                    )

            spending_dict = None
            if message.spending:
                if session.spending is None:
                    spending_dict = message.spending.model_dump()
                else:
                    spending_dict = (session.spending + message.spending).model_dump()

            await self._sessions_repository.update_session(
                session_id=session_id,
                context_size=context_size,
                spending=spending_dict,
            )

    async def get_messages(
        self,
        filter: MessageFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
        from_last_summarization: bool = True,
    ) -> AsyncGenerator[AgentMessage]:
        messages = []
        async for message in self._messages_repository.get_messages(
            filter_=filter,
            pagination=pagination,
            sort=sort,
        ):
            messages.append(message)

        if from_last_summarization:
            index = 0
            for i, message in enumerate(messages):
                if message.role == "summary":
                    index = i
            messages = messages[index:]

        for message in messages:
            yield message

    async def get_spending(self, session_id: uuid.UUID) -> Spending:
        async with self._sessions_repository.transaction():
            session = await self._sessions_repository.get_session(session_id)
            if session is None:
                return Spending()
            return session.spending or Spending()

    async def get_context_size(self, session_id: uuid.UUID) -> int:
        async with self._sessions_repository.transaction():
            session = await self._sessions_repository.get_session(session_id)
            if session is None:
                return 0
            return session.context

    async def get_sessions(
        self,
        filter: SessionFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[uuid.UUID]:
        async for session_id in self._sessions_repository.get_sessions(
            date_filter=filter,
            pagination=pagination,
            sort=sort,
        ):
            yield session_id

    async def get_session(self, session_id: uuid.UUID) -> SessionMetadata | None:
        async with self._sessions_repository.transaction():
            session = await self._sessions_repository.get_session(session_id)

        if session is None:
            return None
        return SessionMetadata(
            id=session.id,
            created_at=session.created_at,
            updated_at=session.updated_at,
            context_size=session.context_size,
            spending=Spending(**session.spending) if session.spending else None,
        )

    async def delete_session(self, session_id: uuid.UUID) -> None:
        raise NotImplementedError
