import asyncio
import datetime
import pathlib
import secrets
import uuid
from typing import AsyncGenerator

import aiofiles

from microclaw.dto import CronTask, User, UserRoleEnum
from microclaw.users_storages.interfaces import UsersStorageInterface
from microclaw.utils import Empty
from .dto import TokenData, UserChannelData, UserData
from .settings import FilesystemUsersStorageSettings


class FilesystemUsersStorage(UsersStorageInterface):
    def __init__(self, settings: FilesystemUsersStorageSettings):
        self._settings = settings
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        self._settings.path.mkdir(parents=True, exist_ok=True)

    async def get_users(self) -> AsyncGenerator[User]:
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                user_data = UserData.model_validate_json(content)
                yield user_data.to_user()
            except Exception:
                continue

    async def create_user(
            self,
            user_id: uuid.UUID | None = None,
            role: UserRoleEnum = UserRoleEnum.USER,
            agent_settings: "AgentSettings | None" = None,  # noqa: F821
    ) -> User:
        if user_id is None:
            user_id = uuid.uuid4()

        user = User(
            id=user_id,
            role=role,
            agent=agent_settings.model_dump() if agent_settings else None,
        )
        await self._write_user(user=user)
        return user

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        user_data = await self._read_user_data(user_id=user_id)
        if user_data:
            return user_data.to_user()
        return None

    async def update_user(
            self,
            user_id: uuid.UUID,
            role: UserRoleEnum | Empty = Empty,
            agent_settings: "AgentSettings | None | Empty" = Empty,  # noqa: F821
    ) -> User | None:
        lock = await self._get_user_lock(user_id=user_id)
        async with lock:
            user_data = await self._read_user_data(user_id=user_id)
            if user_data is None:
                return None

            if not isinstance(role, Empty):
                user_data.role = role
            if not isinstance(agent_settings, Empty):
                user_data.agent = agent_settings.model_dump() if agent_settings else None

            await self._write_user_data(user_data=user_data)
            return user_data.to_user()

    async def delete_user(self, user_id: uuid.UUID):
        lock = await self._get_user_lock(user_id=user_id)
        async with lock:
            user_file = self._get_user_file_path(user_id)
            if not user_file.exists():
                return False

            user_file.unlink()
            for channel_file in self._settings.path.glob("channel_*.json"):
                try:
                    async with aiofiles.open(channel_file, mode="r", encoding="utf-8") as f:
                        content = await f.read()
                    channel_data = UserChannelData.model_validate_json(content)
                    if channel_data.user_id == user_id:
                        channel_file.unlink()
                except Exception:
                    continue

            for token_file in self._settings.path.glob("token_*.json"):
                try:
                    async with aiofiles.open(token_file, mode="r", encoding="utf-8") as f:
                        content = await f.read()
                    token_data = TokenData.model_validate_json(content)
                    if token_data.user_id == user_id:
                        token_file.unlink()
                except Exception:
                    continue

            return True

    async def get_user_by_channel(
            self,
            channel_key: str,
            channel_internal_id: str,
    ) -> User | None:
        channel_data = await self._read_channel(
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )
        if channel_data:
            user_data = await self._read_user_data(user_id=channel_data.user_id)
            if user_data:
                return user_data.to_user()
        return None

    async def get_actual_session(
            self,
            user_id: uuid.UUID,
            channel_key: str,
            channel_internal_id: str,
    ) -> uuid.UUID | None:
        channel_data = await self._read_channel(
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )
        if not channel_data or channel_data.user_id != user_id:
            return None
        if not channel_data.sessions:
            return None
        return channel_data.sessions[-1]

    async def attach_session_to_user(
            self,
            user_id: uuid.UUID,
            session_id: uuid.UUID,
            channel_key: str,
            channel_internal_id: str,
    ) -> None:
        lock = await self._get_lock(
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )
        async with lock:
            channel_data = await self._read_channel(
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
            )
            
            if channel_data is None:
                channel_data = UserChannelData(user_id=user_id, sessions=[])
            elif channel_data.user_id != user_id:
                raise ValueError(
                    f"Channel {channel_key}:{channel_internal_id} "
                    f"is already associated with user {channel_data.user_id}"
                )
            
            if session_id not in channel_data.sessions:
                channel_data.sessions.append(session_id)
            
            await self._write_channel(
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
                data=channel_data,
            )
    
    async def get_user_by_session(self, session_id: uuid.UUID) -> User | None:
        for channel_file in self._settings.path.glob("channel_*.json"):
            try:
                async with aiofiles.open(channel_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                channel_data = UserChannelData.model_validate_json(content)
            except Exception:
                continue

            if session_id in channel_data.sessions:
                user_data = await self._read_user_data(user_id=channel_data.user_id)
                if user_data:
                    return user_data.to_user()
        return None

    async def get_user_by_token(self, token: str) -> User | None:
        token_data = await self._read_token(token=token)
        if token_data:
            user_data = await self._read_user_data(user_id=token_data.user_id)
            if user_data:
                return user_data.to_user()
        return None

    async def _get_lock(
            self,
            channel_key: str,
            channel_internal_id: str,
    ) -> asyncio.Lock:
        lock_key = f"{channel_key}:{channel_internal_id}"
        async with self._global_lock:
            if lock_key not in self._locks:
                self._locks[lock_key] = asyncio.Lock()
            return self._locks[lock_key]

    async def _read_user_data(self, user_id: uuid.UUID) -> UserData | None:
        user_file = self._get_user_file_path(user_id)
        if not user_file.exists():
            return None

        async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
            content = await f.read()
        return UserData.model_validate_json(content)

    async def _write_user_data(self, user_data: UserData) -> None:
        user_file = self._get_user_file_path(user_data.id)

        async with aiofiles.open(user_file, mode="w", encoding="utf-8") as f:
            await f.write(user_data.model_dump_json(indent=2))

    async def _read_user(self, user_id: uuid.UUID) -> User | None:
        user_data = await self._read_user_data(user_id=user_id)
        if user_data:
            return user_data.to_user()
        return None

    async def _write_user(self, user: User) -> None:
        user_data = UserData.from_user(user=user)
        await self._write_user_data(user_data=user_data)

    def _get_user_file_path(self, user_id: uuid.UUID) -> pathlib.Path:
        return self._settings.path / f"user_{user_id}.json"

    async def _read_channel(
            self,
            channel_key: str,
            channel_internal_id: str,
    ) -> UserChannelData | None:
        channel_file = self._get_channel_file_path(
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )
        if not channel_file.exists():
            return None

        async with aiofiles.open(channel_file, mode="r", encoding="utf-8") as f:
            content = await f.read()
        return UserChannelData.model_validate_json(content)

    async def _write_channel(
            self,
            channel_key: str,
            channel_internal_id: str,
            data: UserChannelData,
    ) -> None:
        channel_file = self._get_channel_file_path(
            channel_key=channel_key,
            channel_internal_id=channel_internal_id,
        )

        async with aiofiles.open(channel_file, mode="w", encoding="utf-8") as f:
            await f.write(data.model_dump_json(indent=2))

    def _get_channel_file_path(
            self,
            channel_key: str,
            channel_internal_id: str,
    ) -> pathlib.Path:
        return self._settings.path / f"channel_{channel_key}_{channel_internal_id}.json"

    async def get_crons(self, user_id: uuid.UUID) -> list[CronTask]:
        user_data = await self._read_user_data(user_id=user_id)
        if user_data:
            return user_data.crons
        return []

    async def create_cron(
            self,
            user_id: uuid.UUID,
            cron_task: CronTask,
    ) -> None:
        lock = await self._get_user_lock(user_id=user_id)
        async with lock:
            user_data = await self._read_user_data(user_id=user_id)
            if user_data is None:
                user_data = UserData(id=user_id, role=UserRoleEnum.USER, agent=None, crons=[])
            user_data.crons.append(cron_task)
            await self._write_user_data(user_data=user_data)

    async def remove_cron(self, cron_id: uuid.UUID) -> None:
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                user_data = UserData.model_validate_json(content)
            except Exception:
                continue

            original_count = len(user_data.crons)
            user_data.crons = [c for c in user_data.crons if c.id != cron_id]
            
            if len(user_data.crons) != original_count:
                lock = await self._get_user_lock(user_id=user_data.id)
                async with lock:
                    await self._write_user_data(user_data=user_data)
                break

    async def _get_user_lock(self, user_id: uuid.UUID) -> asyncio.Lock:
        lock_key = f"user_{user_id}"
        async with self._global_lock:
            if lock_key not in self._locks:
                self._locks[lock_key] = asyncio.Lock()
            return self._locks[lock_key]

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
            old_token_data = await self._read_token(token=token)
            if old_token_data is None:
                break

        token_data = TokenData(token=token, user_id=user_id, expires_at=expires_at)
        await self._write_token(token_data=token_data)
        return token

    async def delete_token(self, token: str) -> None:
        token_file = self._get_token_file_path(token)
        if token_file.exists():
            token_file.unlink()

    async def _read_token(self, token: str) -> TokenData | None:
        token_file = self._get_token_file_path(token)
        if not token_file.exists():
            return None

        async with aiofiles.open(token_file, mode="r", encoding="utf-8") as f:
            content = await f.read()
        return TokenData.model_validate_json(content)

    async def _write_token(self, token_data: TokenData) -> None:
        token_file = self._get_token_file_path(token_data.token)

        async with aiofiles.open(token_file, mode="w", encoding="utf-8") as f:
            await f.write(token_data.model_dump_json(indent=2))

    def _get_token_file_path(self, token: str) -> pathlib.Path:
        return self._settings.path / f"token_{token}.json"
