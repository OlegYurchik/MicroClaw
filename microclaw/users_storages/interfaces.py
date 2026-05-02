import uuid
from typing import AsyncGenerator

import facet

from microclaw.dto import CronTask, User


class UsersStorageInterface(facet.AsyncioServiceMixin):
    async def get_users(self) -> AsyncGenerator[User]:
        raise NotImplementedError

    async def create_user(
            self,
            user_id: uuid.UUID | None = None,
            agent_settings: "AgentSettings | None" = None,
    ) -> User:
        raise NotImplementedError

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        raise NotImplementedError

    async def get_user_by_channel(
            self,
            channel_key: str,
            channel_internal_id: str,
    ) -> User | None:
        raise NotImplementedError

    async def get_user_by_session(self, session_id: uuid.UUID) -> User | None:
        raise NotImplementedError

    async def get_actual_session(
            self,
            user_id: uuid.UUID,
            channel_key: str,
            channel_internal_id: str,
    ) -> uuid.UUID | None:
        raise NotImplementedError

    async def attach_session_to_user(
            self,
            user_id: uuid.UUID,
            session_id: uuid.UUID,
            channel_key: str,
            channel_internal_id: str,
    ) -> None:
        raise NotImplementedError

    async def get_crons(self, user_id: uuid.UUID) -> list[CronTask]:
        raise NotImplementedError

    async def create_cron(
            self,
            user_id: uuid.UUID,
            cron_task: CronTask,
    ) -> None:
        raise NotImplementedError

    async def remove_cron(self, cron_id: uuid.UUID) -> None:
        raise NotImplementedError
