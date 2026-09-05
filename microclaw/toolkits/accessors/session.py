from collections.abc import AsyncGenerator
import uuid

from microclaw.dto import AgentMessage
from microclaw.sessions_storages.dto import MessageCreate
from microclaw.sessions_storages.filters import MessageFilter, SessionFilter
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
from microclaw.users_storages.filters import UserChannelFilter
from microclaw.users_storages.interfaces import UsersStorageInterface


class CurrentSessionAccessor:
    def __init__(
        self,
        session_id: uuid.UUID,
        storage: SessionsStorageInterface,
        writable: bool = False,
    ):
        self.session_id = session_id
        self._storage = storage
        self._writable = writable

    def get_messages(self, filter: MessageFilter | None = None) -> AsyncGenerator[AgentMessage, None]:
        if filter is not None:
            _filter = filter.model_copy(update={"session_id": {self.session_id}})
        else:
            _filter = MessageFilter(session_id={self.session_id})
        return self._storage.get_messages(filter_=_filter)

    async def add_message(self, message: AgentMessage) -> None:
        if not self._writable:
            raise PermissionError("Current session write access not granted")
        await self._storage.create_message(
            data=MessageCreate(session_id=self.session_id, message=message)
        )

    async def get_context_size(self) -> int:
        return await self._storage.get_context_size(
            filter_=SessionFilter(id={self.session_id})
        )


class AllSessionsAccessor:
    def __init__(self, storage: SessionsStorageInterface):
        self._storage = storage

    async def get_sessions(self) -> AsyncGenerator[uuid.UUID, None]:
        async for session in self._storage.get_sessions():
            yield session.id

    def get_messages(self, session_id: uuid.UUID, filter: MessageFilter | None = None) -> AsyncGenerator[AgentMessage, None]:
        if filter is not None:
            _filter = filter.model_copy(update={"session_id": {session_id}})
        else:
            _filter = MessageFilter(session_id={session_id})
        return self._storage.get_messages(filter_=_filter)


class UserSessionsAccessor:
    """Provides session lookup for the current user across channels."""

    def __init__(self, user_id: uuid.UUID, storage: UsersStorageInterface):
        self._user_id = user_id
        self._storage = storage

    async def get_user_sessions(
        self, channel_key: str, channel_internal_id: str
    ) -> list[uuid.UUID]:
        channel = await self._storage.get_user_channel(
            filter_=UserChannelFilter(
                user_id={self._user_id},
                channel_key={channel_key},
                channel_internal_id={channel_internal_id},
            )
        )
        if channel is None or channel.actual_session_id is None:
            return []
        return [channel.actual_session_id]

    async def get_actual_session(
        self, channel_key: str, channel_internal_id: str
    ) -> uuid.UUID | None:
        sessions = await self.get_user_sessions(channel_key, channel_internal_id)
        return sessions[0] if sessions else None
