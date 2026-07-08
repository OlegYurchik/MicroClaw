import datetime
import uuid
from typing import AsyncGenerator

import facet

from microclaw.dto import CronTask, User, UserRoleEnum
from microclaw.utils import Empty


class UsersMixin:
    async def get_users(self) -> AsyncGenerator[User]:
        raise NotImplementedError

    async def create_user(
        self,
        user_id: uuid.UUID | None = None,
        role: UserRoleEnum = UserRoleEnum.USER,
        agent_settings: "AgentSettings | None" = None,  # noqa: F821
    ) -> User:
        raise NotImplementedError

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        raise NotImplementedError

    async def update_user(
        self,
        user_id: uuid.UUID,
        role: UserRoleEnum | None | Empty = Empty,
        agent_settings: "AgentSettings | None | Empty" = Empty,  # noqa: F821
    ) -> User | None:
        raise NotImplementedError

    async def delete_user(self, user_id: uuid.UUID) -> bool:
        raise NotImplementedError

    async def get_user_by_channel(
        self,
        channel_key: str,
        channel_internal_id: str,
    ) -> User | None:
        raise NotImplementedError

    async def get_user_by_session(self, session_id: uuid.UUID) -> User | None:
        raise NotImplementedError

    async def get_user_by_token(self, token: str) -> User | None:
        raise NotImplementedError


class SessionsMixin:
    async def get_actual_session(
        self,
        user_id: uuid.UUID,
        channel_key: str,
        channel_internal_id: str,
    ) -> uuid.UUID | None:
        raise NotImplementedError

    async def get_user_sessions(
        self,
        user_id: uuid.UUID,
        channel_key: str,
        channel_internal_id: str,
    ) -> list[uuid.UUID]:
        raise NotImplementedError

    async def attach_session_to_user(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        channel_key: str,
        channel_internal_id: str,
    ) -> None:
        raise NotImplementedError


class CronsMixin:
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


class TokensMixin:
    async def create_token_for_user(
        self,
        user_id: uuid.UUID,
        ttl: datetime.timedelta | None = datetime.timedelta(days=30),
    ) -> str:
        raise NotImplementedError

    async def delete_token(self, token: str):
        raise NotImplementedError


class UsersStorageInterface(
    facet.AsyncioServiceMixin,
    UsersMixin,
    SessionsMixin,
    CronsMixin,
    TokensMixin,
):
    pass
