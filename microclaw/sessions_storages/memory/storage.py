from collections.abc import AsyncGenerator
import uuid

from .settings import MemorySessionsStorageSettings
from pydantic_filters import BaseSort, SortByOrder
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.dto import AgentMessage, SessionMetadata, Spending
from microclaw.sessions_storages.filters import MessageFilter, SessionFilter
from microclaw.sessions_storages.interfaces import SessionsStorageInterface


class MemorySessionsStorage(SessionsStorageInterface):
    def __init__(self, settings: MemorySessionsStorageSettings):
        self._messages: dict[uuid.UUID, list[AgentMessage]] = {}
        self._spendings: dict[uuid.UUID, Spending] = {}
        self._context: dict[uuid.UUID, int] = {}
        self._sessions: dict[uuid.UUID, dict] = {}

    async def create_session(self, session_id: uuid.UUID | None = None) -> uuid.UUID:
        if session_id is None:
            session_id = uuid.uuid4()

        if session_id not in self._messages:
            self._messages[session_id] = []
        if session_id not in self._context:
            self._context[session_id] = 0
        if session_id not in self._sessions:
            import datetime

            self._sessions[session_id] = {
                "id": session_id,
                "created_at": datetime.datetime.now(),
                "updated_at": datetime.datetime.now(),
            }

        return session_id

    async def add_message(self, session_id: uuid.UUID, message: AgentMessage):
        if session_id not in self._messages:
            self._messages[session_id] = []
        if session_id not in self._context:
            self._context[session_id] = 0

        self._messages[session_id].append(message)
        if not message.spending:
            return

        if message.role == "summary":
            self._context[session_id] = message.spending.output_tokens
        elif message.context_tokens is not None:
            self._context[session_id] = message.context_tokens
        else:
            self._context[session_id] = (
                message.spending.input_tokens + message.spending.output_tokens
            )

        if session_id in self._spendings:
            self._spendings[session_id] += message.spending
        else:
            self._spendings[session_id] = message.spending

        if session_id in self._sessions:
            import datetime

            self._sessions[session_id]["updated_at"] = datetime.datetime.now()

    async def get_sessions(
        self,
        filter: SessionFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[uuid.UUID]:
        sessions = list(self._sessions.keys())

        if filter is not None and filter.id is not None:
            sessions = [s for s in sessions if s == filter.id]

        if sort is not None and sort.sort_by is not None:
            sort_field = sort.sort_by
            reverse = sort.sort_by_order == SortByOrder.desc

            if sort_field == "id":
                sessions.sort(reverse=reverse)
            elif sort_field in ["created_at", "updated_at"]:
                sessions.sort(
                    key=lambda s: self._sessions[s].get(sort_field), reverse=reverse
                )

        if pagination and pagination.limit is not None:
            page_offset = pagination.offset if pagination else 0
            page_limit = pagination.limit if pagination else None
            end_index = (
                min(page_offset + page_limit, len(sessions))
                if page_limit
                else len(sessions)
            )
            sessions = sessions[page_offset:end_index]

        for session_id in sessions:
            yield session_id

    async def get_messages(
        self,
        filter: MessageFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
        from_last_summarization: bool = True,
    ) -> AsyncGenerator[AgentMessage]:
        if filter is None or filter.session_id is None:
            return

        session_id = filter.session_id
        if session_id not in self._messages:
            return

        messages = list(self._messages[session_id])

        if filter.role is not None:
            messages = [m for m in messages if m.role == filter.role]

        if sort is not None and sort.sort_by is not None:
            sort_field = sort.sort_by
            reverse = sort.sort_by_order == SortByOrder.desc

            if sort_field == "role":
                messages.sort(key=lambda m: m.role, reverse=reverse)

        if pagination and pagination.limit is not None:
            page_offset = pagination.offset if pagination else 0
            page_limit = pagination.limit if pagination else None
            end_index = (
                min(page_offset + page_limit, len(messages))
                if page_limit
                else len(messages)
            )
            messages = messages[page_offset:end_index]

        if from_last_summarization:
            index = 0
            for i, message in enumerate(messages):
                if message.role == "summary":
                    index = i
        else:
            index = 0

        for message in messages[index:]:
            yield message

    async def get_spending(self, session_id: uuid.UUID) -> Spending:
        return self._spendings.get(session_id, Spending())

    async def get_context_size(self, session_id: uuid.UUID) -> int:
        return self._context.get(session_id, 0)

    async def get_session(self, session_id: uuid.UUID) -> SessionMetadata | None:
        if session_id not in self._sessions:
            return None

        session = self._sessions[session_id]
        return SessionMetadata(
            id=session_id,
            created_at=session.get("created_at"),
            updated_at=session.get("updated_at"),
            context_size=self._context.get(session_id, 0),
            spending=self._spendings.get(session_id),
        )

    async def delete_session(self, session_id: uuid.UUID) -> None:
        if session_id not in self._sessions:
            return

        self._sessions.pop(session_id, None)
        self._messages.pop(session_id, None)
        self._spendings.pop(session_id, None)
        self._context.pop(session_id, None)
