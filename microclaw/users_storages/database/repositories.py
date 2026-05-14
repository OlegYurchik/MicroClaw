import datetime
import uuid
from typing import AsyncGenerator

from pydantic_filters import BasePagination

from microclaw.dto import CronTask, UserRoleEnum
from microclaw.utils import Empty
from microclaw.utils.database.base import BaseRepository
from microclaw.utils.database.tables import BaseTable

from .dto import CronData, SessionData, TokenData, UserData
from .filters import CronFilter, SessionFilter, TokenFilter, UserFilter
from .tables import CronTable, SessionTable, TokenTable, UserTable


class UsersRepository(BaseRepository[UserData, UserFilter]):
    def get_db_table(self) -> type[BaseTable]:
        return UserTable

    async def get_user(self, user_id: uuid.UUID) -> UserData | None:
        async for item in self.get_items(filter_=UserFilter(id=user_id)):
            return item
        return None

    async def get_users(self) -> AsyncGenerator[UserData]:
        async for item in self.get_items():
            yield item

    async def create_user(self, user_id: uuid.UUID, role: UserRoleEnum = UserRoleEnum.USER) -> UserData:
        user_data = UserData(id=user_id, role=role, agent=None)
        return await self.create_item(user_data)

    async def update_user(
            self,
            user_id: uuid.UUID,
            role: UserRoleEnum | Empty = Empty,
            agent: dict | None | Empty = Empty,
    ) -> UserData | None:
        values = {}
        if not isinstance(role, Empty):
            values["role"] = role
        if not isinstance(agent, Empty):
            values["agent"] = agent

        if not values:
            return await self.get_user(user_id=user_id)

        async for item in self.update_items(filter_=UserFilter(id=user_id), **values):
            return item
        return None

    async def delete_user(self, user_id: uuid.UUID):
        await self.delete_items(filter_=UserFilter(id=user_id))


class SessionsRepository(BaseRepository[SessionData, SessionFilter]):
    def get_db_table(self) -> type[BaseTable]:
        return SessionTable

    async def get_session(
        self,
        channel_key: str,
        channel_internal_id: str,
    ) -> SessionData | None:
        async for item in self.get_items(
            filter_=SessionFilter(
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
            ),
        ):
            return item
        return None

    async def get_sessions_by_user(
        self,
        user_id: uuid.UUID,
    ) -> AsyncGenerator[SessionData]:
        async for item in self.get_items(filter_=SessionFilter(user_id=user_id)):
            yield item

    async def create_session(
        self,
        user_id: uuid.UUID,
        channel_key: str,
        channel_internal_id: str,
        session_id: uuid.UUID | None = None,
    ) -> SessionData:
        if session_id is None:
            session_id = uuid.uuid4()
        session_data = SessionData(
            id=session_id,
            user_id=user_id,
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )
        return await self.create_item(session_data)

    async def get_session_by_id(self, session_id: uuid.UUID) -> SessionData | None:
        async for item in self.get_items(filter_=SessionFilter(id=session_id)):
            return item
        return None

    async def get_actual_session(
        self,
        user_id: uuid.UUID,
        channel_key: str,
        channel_internal_id: str,
    ) -> SessionData | None:
        filter_ = SessionFilter(
            user_id=user_id,
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )
        async for item in self.get_items(filter_=filter_, pagination=BasePagination(limit=1, offset=0)):
            return item
        return None


class CronsRepository(BaseRepository[CronData, CronFilter]):
    def get_db_table(self) -> type[BaseTable]:
        return CronTable

    async def get_user_crons(
        self,
        user_id: uuid.UUID,
    ) -> AsyncGenerator[CronData]:
        async for item in self.get_items(filter_=CronFilter(user_id=user_id)):
            yield item

    async def create_user_cron(
        self,
        user_id: uuid.UUID,
        cron_task: CronTask,
    ) -> CronData:
        cron_data = CronData.from_cron_task(cron_task=cron_task, user_id=user_id)
        return await self.create_item(cron_data)

    async def delete_user_cron(
        self,
        cron_id: uuid.UUID,
    ) -> None:
        await self.delete_items(filter_=CronFilter(id=cron_id))


class TokensRepository(BaseRepository[TokenData, TokenFilter]):
    def get_db_table(self) -> type[BaseTable]:
        return TokenTable

    async def get_token(self, token: str) -> TokenData | None:
        async for item in self.get_items(filter_=TokenFilter(token=token)):
            return item
        return None

    async def create_token(
            self,
            token: str,
            user_id: uuid.UUID,
            expires_at: datetime.datetime | None = None,
    ) -> TokenData:
        token_data = TokenData(token=token, user_id=user_id, expires_at=expires_at)
        return await self.create_item(token_data)

    async def delete_token(self, token: str) -> None:
        await self.delete_items(filter_=TokenFilter(token=token))
