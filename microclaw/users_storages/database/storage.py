import datetime
import secrets
import uuid
from typing import AsyncGenerator

from microclaw.dto import CronTask, User, UserRoleEnum
from microclaw.users_storages.interfaces import UsersStorageInterface
from microclaw.utils import Empty

from .repositories import CronsRepository, SessionsRepository, TokensRepository, UsersRepository
from .settings import DatabaseUsersStorageSettings
from .tables import UserTable


class DatabaseUsersStorage(UsersStorageInterface):
    def __init__(self, settings: DatabaseUsersStorageSettings):
        self._settings = settings
        self._users_repository = UsersRepository(settings=settings)
        self._sessions_repository = SessionsRepository(settings=settings)
        self._crons_repository = CronsRepository(settings=settings)
        self._tokens_repository = TokensRepository(settings=settings)

    async def start(self):
        async with self._users_repository._engine.begin() as conn:
            await conn.run_sync(UserTable.metadata.create_all)

    async def stop(self):
        pass

    async def get_users(self) -> AsyncGenerator[User]:
        async with self._users_repository.transaction():
            async for user_data in self._users_repository.get_users():
                yield user_data.to_user()

    async def create_user(
            self,
            user_id: uuid.UUID | None = None,
            role: UserRoleEnum = UserRoleEnum.USER,
            agent_settings: "AgentSettings | None" = None,  # noqa: F821
    ) -> User:
        if user_id is None:
            user_id = uuid.uuid4()

        async with self._users_repository.transaction():
            user_data = await self._users_repository.create_user(user_id=user_id, role=role)

        return user_data.to_user()

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        async with self._users_repository.transaction():
            user_data = await self._users_repository.get_user(user_id=user_id)
            if user_data:
                return user_data.to_user()
        return None

    async def update_user(
            self,
            user_id: uuid.UUID,
            role: UserRoleEnum | None | Empty = Empty,
            agent_settings: "AgentSettings | None | Empty" = Empty,  # noqa: F821
    ) -> User | None:
        async with self._users_repository.transaction():
            user_data = await self._users_repository.update_user(
                user_id=user_id,
                role=role,
                agent=agent_settings,
            )
            if user_data:
                return user_data.to_user()
        return None

    async def delete_user(self, user_id: uuid.UUID):
        async with self._users_repository.transaction():
            await self._users_repository.delete_user(user_id=user_id)

    async def get_user_by_channel(
            self,
            channel_key: str,
            channel_internal_id: str,
    ) -> User | None:
        async with self._sessions_repository.transaction():
            session_data = await self._sessions_repository.get_session(
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
            )
            if not session_data:
                return None
            user_data = await self._users_repository.get_user(
                user_id=session_data.user_id,
            )
            if not user_data:
                return None
            return user_data.to_user()

    async def get_user_by_session(self, session_id: uuid.UUID) -> User | None:
        async with self._sessions_repository.transaction():
            session_data = await self._sessions_repository.get_session_by_id(session_id=session_id)
            if not session_data:
                return None
            user_data = await self._users_repository.get_user(user_id=session_data.user_id)
            if not user_data:
                return None
            return user_data.to_user()

    async def get_user_by_token(self, token: str) -> User | None:
        async with self._tokens_repository.transaction():
            token_data = await self._tokens_repository.get_token(token=token)
            if not token_data:
                return None
            user_data = await self._users_repository.get_user(user_id=token_data.user_id)
            if not user_data:
                return None
            return user_data.to_user()

    async def get_actual_session(
            self,
            user_id: uuid.UUID,
            channel_key: str,
            channel_internal_id: str,
    ) -> uuid.UUID | None:
        async with self._sessions_repository.transaction():
            session_data = await self._sessions_repository.get_actual_session(
                user_id=user_id,
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
            )
            if not session_data:
                return None
        return session_data.id

    async def attach_session_to_user(
            self,
            user_id: uuid.UUID,
            session_id: uuid.UUID,
            channel_key: str,
            channel_internal_id: str,
    ) -> None:
        async with self._sessions_repository.transaction():
            existing_session = await self._sessions_repository.get_session(
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
            )
            if existing_session:
                return
            await self._sessions_repository.create_session(
                user_id=user_id,
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
                session_id=session_id,
            )

    async def get_crons(self, user_id: uuid.UUID) -> list[CronTask]:
        async with self._crons_repository.transaction():
            crons = []
            async for cron_data in self._crons_repository.get_user_crons(user_id=user_id):
                crons.append(cron_data.to_cron_task())
            return crons

    async def create_cron(
            self,
            user_id: uuid.UUID,
            cron_task: CronTask,
    ) -> None:
        async with self._crons_repository.transaction():
            await self._crons_repository.create_user_cron(
                user_id=user_id,
                cron_task=cron_task,
            )

    async def remove_cron(self, cron_id: uuid.UUID) -> None:
        async with self._crons_repository.transaction():
            await self._crons_repository.delete_user_cron(cron_id=cron_id)

    async def create_token_for_user(
            self,
            user_id: uuid.UUID,
            ttl: datetime.timedelta | None = datetime.timedelta(days=30),
    ) -> str:
        expires_at = None
        if ttl is not None:
            expires_at = datetime.datetime.now(datetime.timezone.utc) + ttl

        while True:
            token = secrets.token_urlsafe(32)
            async with self._tokens_repository.transaction():
                old_token = self._tokens_repository.get_token(token=token)
            if old_token is None:
                break

        async with self._tokens_repository.transaction():
            await self._tokens_repository.create_token(
                token=token,
                user_id=user_id,
                expires_at=expires_at,
            )
        return token

    async def delete_token(self, token: str) -> None:
        async with self._tokens_repository.transaction():
            await self._tokens_repository.delete_token(token=token)
