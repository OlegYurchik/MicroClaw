import uuid
from typing import AsyncGenerator, Callable

from microclaw.agents.settings import AgentSettings
from microclaw.dto import CronTask, User
from microclaw.users_storages.interfaces import UsersStorageInterface


class CurrentUserAccessor:
    def __init__(
        self,
        user_id: uuid.UUID,
        storage: UsersStorageInterface,
        writable: bool = False,
        invalidate_cache: Callable[[], None] | None = None,
    ):
        self.user_id = user_id
        self._storage = storage
        self._writable = writable
        self._invalidate_cache = invalidate_cache

    async def get(self) -> User | None:
        return await self._storage.get_user(self.user_id)

    async def get_crons(self) -> list[CronTask]:
        return await self._storage.get_crons(self.user_id)

    async def update_agent_settings(
        self, agent_settings: AgentSettings | None
    ) -> User | None:
        if not self._writable:
            raise PermissionError("Current user write access not granted")
        result = await self._storage.update_user(
            user_id=self.user_id, agent_settings=agent_settings
        )
        if self._invalidate_cache:
            self._invalidate_cache()
        return result

    async def create_cron(self, cron_task: CronTask) -> None:
        if not self._writable:
            raise PermissionError("Current user write access not granted")
        return await self._storage.create_cron(self.user_id, cron_task)

    async def remove_cron(self, cron_id: uuid.UUID) -> None:
        if not self._writable:
            raise PermissionError("Current user write access not granted")
        crons = await self._storage.get_crons(self.user_id)
        if not any(c.id == cron_id for c in crons):
            raise PermissionError(
                f"Cron {cron_id} not found or not owned by current user"
            )
        return await self._storage.remove_cron(cron_id)


class AllUsersAccessor:
    def __init__(self, storage: UsersStorageInterface, writable: bool = False):
        self._storage = storage
        self._writable = writable

    @property
    def writable(self) -> bool:
        return self._writable

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._storage.get_user(user_id)

    async def get_by_session(self, session_id: uuid.UUID) -> User | None:
        return await self._storage.get_user_by_session(session_id)

    async def get_by_channel(
        self, channel_key: str, channel_internal_id: str
    ) -> User | None:
        return await self._storage.get_user_by_channel(channel_key, channel_internal_id)

    async def get_users(self) -> AsyncGenerator[User, None]:
        return self._storage.get_users()

    async def get_crons(self, user_id: uuid.UUID) -> list[CronTask]:
        return await self._storage.get_crons(user_id)

    async def create_cron(self, user_id: uuid.UUID, cron_task: CronTask) -> None:
        if not self._writable:
            raise PermissionError("All users write access not granted")
        await self._storage.create_cron(user_id, cron_task)

    async def remove_cron(self, cron_id: uuid.UUID) -> None:
        if not self._writable:
            raise PermissionError("All users write access not granted")
        await self._storage.remove_cron(cron_id)

    async def update_agent_settings(
        self, user_id: uuid.UUID, agent_settings: AgentSettings | None
    ) -> User | None:
        if not self._writable:
            raise PermissionError("All users write access not granted")
        return await self._storage.update_user(
            user_id=user_id, agent_settings=agent_settings
        )
