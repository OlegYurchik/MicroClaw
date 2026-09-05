from collections.abc import AsyncGenerator, Callable
from typing import Any
import uuid

from pydantic import BaseModel

from microclaw.agents.settings import AgentSettings
from microclaw.dto import CronTask, User
from microclaw.users_storages.dto import CronCreate, UserUpdate
from microclaw.users_storages.filters import CronFilter, UserChannelFilter, UserFilter
from microclaw.users_storages.interfaces import UsersStorageInterface
from microclaw.users_storages.utils import get_user_by_session


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
        return await self._storage.get_user(
            filter_=UserFilter(id={self.user_id})
        )

    async def get_crons(self) -> list[CronTask]:
        return [
            cron async for cron in self._storage.get_crons(
                filter_=CronFilter(user_id={self.user_id})
            )
        ]

    async def update_agent_settings(
        self, agent_settings: AgentSettings | dict[str, Any] | None
    ) -> User | None:
        if not self._writable:
            raise PermissionError("Current user write access not granted")
        agent = None
        if agent_settings is not None:
            if isinstance(agent_settings, BaseModel):
                agent = agent_settings.model_dump(mode="json")
            else:
                agent = agent_settings
        result = await self._storage.update_user(
            filter_=UserFilter(id={self.user_id}),
            data=UserUpdate(agent=agent),
        )
        if self._invalidate_cache:
            self._invalidate_cache()
        return result

    async def create_cron(self, cron_task: CronTask) -> None:
        if not self._writable:
            raise PermissionError("Current user write access not granted")
        await self._storage.create_cron(
            data=CronCreate(
                id=cron_task.id,
                user_id=self.user_id,
                path=cron_task.path,
                cron=cron_task.cron,
                enabled=cron_task.enabled,
                args=cron_task.args,
            )
        )

    async def remove_cron(self, cron_id: uuid.UUID) -> None:
        if not self._writable:
            raise PermissionError("Current user write access not granted")
        crons = await self.get_crons()
        if not any(c.id == cron_id for c in crons):
            raise PermissionError(
                f"Cron {cron_id} not found or not owned by current user"
            )
        return await self._storage.delete_cron(
            filter_=CronFilter(id={cron_id})
        )


class AllUsersAccessor:
    def __init__(self, storage: UsersStorageInterface, writable: bool = False):
        self._storage = storage
        self._writable = writable

    @property
    def writable(self) -> bool:
        return self._writable

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._storage.get_user(
            filter_=UserFilter(id={user_id})
        )

    async def get_by_session(self, session_id: uuid.UUID) -> User | None:
        return await get_user_by_session(self._storage, session_id)

    async def get_by_channel(
        self, channel_key: str, channel_internal_id: str
    ) -> User | None:
        channel = await self._storage.get_user_channel(
            filter_=UserChannelFilter(
                channel_key={channel_key},
                channel_internal_id={channel_internal_id},
            )
        )
        if channel is None:
            return None
        return await self._storage.get_user(
            filter_=UserFilter(id={channel.user_id})
        )

    async def get_users(self) -> AsyncGenerator[User, None]:
        async for user in self._storage.get_users():
            yield user

    async def get_crons(self, user_id: uuid.UUID) -> list[CronTask]:
        return [
            cron async for cron in self._storage.get_crons(
                filter_=CronFilter(user_id={user_id})
            )
        ]

    async def create_cron(self, user_id: uuid.UUID, cron_task: CronTask) -> None:
        if not self._writable:
            raise PermissionError("All users write access not granted")
        await self._storage.create_cron(
            data=CronCreate(
                id=cron_task.id,
                user_id=user_id,
                path=cron_task.path,
                cron=cron_task.cron,
                enabled=cron_task.enabled,
                args=cron_task.args,
            )
        )

    async def remove_cron(self, cron_id: uuid.UUID) -> None:
        if not self._writable:
            raise PermissionError("All users write access not granted")
        await self._storage.delete_cron(
            filter_=CronFilter(id={cron_id})
        )

    async def update_agent_settings(
        self, user_id: uuid.UUID, agent_settings: AgentSettings | dict[str, Any] | None
    ) -> User | None:
        if not self._writable:
            raise PermissionError("All users write access not granted")
        agent = None
        if agent_settings is not None:
            if isinstance(agent_settings, BaseModel):
                agent = agent_settings.model_dump(mode="json")
            else:
                agent = agent_settings
        return await self._storage.update_user(
            filter_=UserFilter(id={user_id}),
            data=UserUpdate(agent=agent),
        )
