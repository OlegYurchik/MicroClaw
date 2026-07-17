import uuid
from typing import AsyncGenerator

from microclaw.dto import AgentMessage
from microclaw.sessions_storages.filters import MessageFilter
from microclaw.sessions_storages.interfaces import SessionsStorageInterface
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

    def get_messages(self, filter: MessageFilter | None = None):
        _filter = filter or MessageFilter(session_id=self.session_id)
        _filter.session_id = self.session_id
        return self._storage.get_messages(filter=_filter)

    async def add_message(self, message: AgentMessage) -> None:
        if not self._writable:
            raise PermissionError("Current session write access not granted")
        await self._storage.add_message(self.session_id, message)

    async def get_context_size(self) -> int:
        return await self._storage.get_context_size(self.session_id)


class AllSessionsAccessor:
    def __init__(self, storage: SessionsStorageInterface):
        self._storage = storage

    def get_sessions(self) -> AsyncGenerator[uuid.UUID, None]:
        return self._storage.get_sessions()

    def get_messages(self, session_id: uuid.UUID, filter: MessageFilter | None = None):
        _filter = filter or MessageFilter(session_id=session_id)
        _filter.session_id = session_id
        return self._storage.get_messages(filter=_filter)


class UserSessionsAccessor:
    """Provides session lookup for the current user across channels."""

    def __init__(self, user_id: uuid.UUID, storage: UsersStorageInterface):
        self._user_id = user_id
        self._storage = storage

    async def get_user_sessions(
        self, channel_key: str, channel_internal_id: str
    ) -> list[uuid.UUID]:
        return await self._storage.get_user_sessions(
            user_id=self._user_id,
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )

    async def get_actual_session(
        self, channel_key: str, channel_internal_id: str
    ) -> uuid.UUID | None:
        return await self._storage.get_actual_session(
            user_id=self._user_id,
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )
