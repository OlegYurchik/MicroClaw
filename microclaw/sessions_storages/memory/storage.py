from collections.abc import AsyncGenerator
import uuid

from .settings import MemorySessionsStorageSettings
from metaorm import AlreadyExistsError, NotFoundError
from pydantic_filters import BaseSort, SortByOrder
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.dto import AgentMessage, AgentMessageRoleEnum, Session, Spending
from microclaw.sessions_storages.dto import (
    MessageCreate,
    MessageUpdate,
    SessionCreate,
    SessionUpdate,
)
from microclaw.sessions_storages.filters import MessageFilter, SessionFilter
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.utils import utcnow


class MemorySessionsStorage(SessionsStorageInterface):
    def __init__(self, settings: MemorySessionsStorageSettings):
        self._messages: dict[uuid.UUID, list[AgentMessage]] = {}
        self._spendings: dict[uuid.UUID, Spending] = {}
        self._context: dict[uuid.UUID, int] = {}
        self._sessions: dict[uuid.UUID, dict] = {}

    async def create_session(
        self,
        data: SessionCreate,
    ) -> Session:
        session_id = data.id
        channel_key = data.channel_key
        channel_internal_id = data.channel_internal_id

        if session_id in self._sessions:
            raise AlreadyExistsError(f"Session {session_id} already exists")

        self._messages[session_id] = []
        self._context[session_id] = 0
        now = utcnow()
        self._sessions[session_id] = {
            "id": session_id,
            "created_at": now,
            "updated_at": now,
            "channel_key": channel_key,
            "channel_internal_id": channel_internal_id,
        }

        return await self.get_session(filter_=SessionFilter(id={session_id}))

    async def get_session(
        self,
        filter_: SessionFilter,
        sort: BaseSort | None = None,
    ) -> Session | None:
        session_id = next(iter(filter_.id), None)
        if session_id is None:
            return None
        if session_id not in self._sessions:
            return None
        session = self._sessions[session_id]
        return Session(
            id=session_id,
            channel_key=session.get("channel_key", ""),
            channel_internal_id=session.get("channel_internal_id", ""),
            context_size=self._context.get(session_id, 0),
            spending=self._spendings.get(session_id),
            created_at=session.get("created_at"),
            updated_at=session.get("updated_at"),
        )

    async def get_sessions(
        self,
        filter_: SessionFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[Session]:
        sessions = list(self._sessions.keys())

        if filter_ is not None:
            if filter_.id:
                sessions = [s for s in sessions if s in filter_.id]
            if filter_.channel_key:
                sessions = [
                    s for s in sessions
                    if self._sessions[s].get("channel_key") in filter_.channel_key
                ]
            if filter_.created_at__gt is not None or filter_.created_at__lt is not None:
                filtered = []
                for s in sessions:
                    created_at = self._sessions[s].get("created_at")
                    if created_at is None:
                        continue
                    if filter_.created_at__gt is not None and created_at <= filter_.created_at__gt:
                        continue
                    if filter_.created_at__lt is not None and created_at >= filter_.created_at__lt:
                        continue
                    filtered.append(s)
                sessions = filtered
            if filter_.updated_at__gt is not None or filter_.updated_at__lt is not None:
                filtered = []
                for s in sessions:
                    updated_at = self._sessions[s].get("updated_at")
                    if updated_at is None:
                        continue
                    if filter_.updated_at__gt is not None and updated_at <= filter_.updated_at__gt:
                        continue
                    if filter_.updated_at__lt is not None and updated_at >= filter_.updated_at__lt:
                        continue
                    filtered.append(s)
                sessions = filtered

        if sort is not None and sort.sort_by is not None:
            sort_field = sort.sort_by
            reverse = sort.sort_by_order == SortByOrder.desc

            if sort_field == "id":
                sessions.sort(reverse=reverse)
            elif sort_field == "channel_key":
                sessions.sort(
                    key=lambda s: self._sessions[s].get("channel_key", ""), reverse=reverse
                )
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
            yield await self.get_session(filter_=SessionFilter(id={session_id}))

    def _session_matches_filter(self, session_id: uuid.UUID, filter_: SessionFilter | None) -> bool:
        if filter_ is None:
            return True
        if filter_.id and session_id not in filter_.id:
            return False
        if filter_.channel_key and self._sessions[session_id].get("channel_key") not in filter_.channel_key:
            return False
        created_at = self._sessions[session_id].get("created_at")
        if created_at is not None:
            if filter_.created_at__gt is not None and created_at <= filter_.created_at__gt:
                return False
            if filter_.created_at__lt is not None and created_at >= filter_.created_at__lt:
                return False
        updated_at = self._sessions[session_id].get("updated_at")
        if updated_at is not None:
            if filter_.updated_at__gt is not None and updated_at <= filter_.updated_at__gt:
                return False
            if filter_.updated_at__lt is not None and updated_at >= filter_.updated_at__lt:
                return False
        return True

    async def update_sessions(
        self,
        filter_: SessionFilter | None = None,
        *, data: SessionUpdate,
    ) -> AsyncGenerator[Session]:
        for session_id in list(self._sessions.keys()):
            if not self._session_matches_filter(session_id, filter_):
                continue
            if data.context_size is not None:
                self._context[session_id] = data.context_size
            if data.spending is not None:
                self._spendings[session_id] = data.spending
            self._sessions[session_id]["updated_at"] = utcnow()
            yield await self.get_session(filter_=SessionFilter(id={session_id}))

    async def delete_session(self, filter_: SessionFilter) -> None:
        session_id = next(iter(filter_.id), None)
        if session_id is None:
            return
        if session_id not in self._sessions:
            return
        self._sessions.pop(session_id, None)
        self._messages.pop(session_id, None)
        self._spendings.pop(session_id, None)
        self._context.pop(session_id, None)

    async def delete_sessions(self, filter_: SessionFilter | None = None) -> None:
        to_delete = []
        for session_id in list(self._sessions.keys()):
            if not self._session_matches_filter(session_id, filter_):
                continue
            to_delete.append(session_id)
        for session_id in to_delete:
            await self.delete_session(filter_=SessionFilter(id={session_id}))

    async def create_message(self, data: MessageCreate) -> AgentMessage:
        if data.session_id not in self._sessions:
            raise NotFoundError(f"Session {data.session_id} not found")

        if data.session_id not in self._messages:
            self._messages[data.session_id] = []
        if data.session_id not in self._context:
            self._context[data.session_id] = 0

        message = data.message
        if message.id is None:
            message = message.model_copy(update={"id": uuid.uuid4()})
        self._messages[data.session_id].append(message)
        if not message.spending:
            return message

        if message.role == AgentMessageRoleEnum.SUMMARY:
            self._context[data.session_id] = message.spending.output_tokens
        elif message.context_tokens is not None:
            self._context[data.session_id] = message.context_tokens
        else:
            self._context[data.session_id] = (
                message.spending.input_tokens + message.spending.output_tokens
            )

        if data.session_id in self._spendings:
            self._spendings[data.session_id] += message.spending
        else:
            self._spendings[data.session_id] = message.spending

        if data.session_id in self._sessions:
            self._sessions[data.session_id]["updated_at"] = utcnow()

        return message

    async def get_message(
        self,
        filter_: MessageFilter,
        sort: BaseSort | None = None,
    ) -> AgentMessage | None:
        async for message in self.get_messages(filter_=filter_, pagination=BasePagination(limit=1, offset=0), sort=sort):
            return message
        return None

    async def get_messages(
        self,
        filter_: MessageFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[AgentMessage]:
        if filter_ is not None and filter_.session_id:
            session_ids = list(filter_.session_id)
        else:
            session_ids = list(self._messages.keys())

        all_messages: list[tuple[uuid.UUID, AgentMessage]] = []
        for session_id in session_ids:
            if session_id not in self._messages:
                continue
            for message in self._messages[session_id]:
                all_messages.append((session_id, message))

        if filter_ is not None and filter_.id:
            all_messages = [
                (sid, m) for sid, m in all_messages if m.id in filter_.id
            ]

        if filter_ is not None and filter_.role:
            all_messages = [
                (sid, m) for sid, m in all_messages if m.role in filter_.role
            ]

        if sort is not None and sort.sort_by is not None:
            sort_field = sort.sort_by
            reverse = sort.sort_by_order == SortByOrder.desc

            if sort_field == "role":
                all_messages.sort(key=lambda item: item[1].role, reverse=reverse)

        if pagination and pagination.limit is not None:
            page_offset = pagination.offset if pagination else 0
            page_limit = pagination.limit if pagination else None
            end_index = (
                min(page_offset + page_limit, len(all_messages))
                if page_limit
                else len(all_messages)
            )
            all_messages = all_messages[page_offset:end_index]

        for _, message in all_messages:
            yield message

    async def update_messages(
        self,
        filter_: MessageFilter | None = None,
        *, data: MessageUpdate,
    ) -> AsyncGenerator[AgentMessage]:
        if filter_ is not None and filter_.session_id:
            session_ids = list(filter_.session_id)
        else:
            session_ids = list(self._messages.keys())

        for session_id in session_ids:
            if session_id not in self._messages:
                continue
            new_messages: list[AgentMessage] = []
            yielded_messages: list[AgentMessage] = []
            for message in self._messages[session_id]:
                if filter_ is not None and filter_.id and message.id not in filter_.id:
                    new_messages.append(message)
                    continue
                if filter_ is not None and filter_.role and message.role not in filter_.role:
                    new_messages.append(message)
                    continue
                update = {}
                if data.role is not None:
                    update["role"] = data.role
                if data.text is not None:
                    update["text"] = data.text
                if update:
                    message = message.model_copy(update=update)
                new_messages.append(message)
                yielded_messages.append(message)
            self._messages[session_id] = new_messages
            for message in yielded_messages:
                yield message

    async def delete_message(self, filter_: MessageFilter) -> None:
        await self.delete_messages(filter_=filter_)

    async def delete_messages(self, filter_: MessageFilter | None = None) -> None:
        if filter_ is not None and filter_.session_id:
            session_ids = list(filter_.session_id)
        else:
            session_ids = list(self._messages.keys())

        for session_id in session_ids:
            if session_id not in self._messages:
                continue
            if filter_ is not None and filter_.id:
                self._messages[session_id] = [
                    m for m in self._messages[session_id]
                    if m.id not in filter_.id
                ]
            elif filter_ is not None and filter_.role:
                self._messages[session_id] = [
                    m for m in self._messages[session_id]
                    if m.role not in filter_.role
                ]
            else:
                self._messages[session_id] = []
