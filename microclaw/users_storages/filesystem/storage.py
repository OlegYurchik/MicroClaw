import asyncio
from collections.abc import AsyncGenerator
import json
import pathlib
import secrets
import uuid

from .dto import TokenData, UserChannelData, UserData
from .settings import FilesystemUsersStorageSettings
import aiofiles
import pydantic
from pydantic_filters import BaseSort, SortByOrder
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.dto import CronTask, Token, User, UserChannel, UserRoleEnum, Webhook
from microclaw.users_storages.dto import (
    CronCreate,
    CronUpdate,
    TokenCreate,
    TokenUpdate,
    UserChannelCreate,
    UserChannelUpdate,
    UserCreate,
    UserUpdate,
    WebhookCreate,
    WebhookUpdate,
)
from microclaw.users_storages.exceptions import AlreadyExistsError
from microclaw.users_storages.filters import (
    CronFilter,
    TokenFilter,
    UserChannelFilter,
    UserFilter,
    WebhookFilter,
)
from microclaw.users_storages.interfaces import UsersStorageInterface


class FilesystemUsersStorage(UsersStorageInterface):
    def __init__(self, settings: FilesystemUsersStorageSettings):
        self._settings = settings
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        self._settings.path.mkdir(parents=True, exist_ok=True)

    async def get_user(
        self,
        filter_: UserFilter,
        sort: BaseSort | None = None,
    ) -> User | None:
        user_id = next(iter(filter_.id), None)
        if user_id is None:
            return None
        user_data = await self._read_user_data(user_id=user_id)
        if user_data:
            return user_data.to_user()
        return None

    async def get_users(
        self,
        filter_: UserFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[User]:
        users: list[User] = []
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                user_data = UserData.model_validate_json(content)
                users.append(user_data.to_user())
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue

        if filter_ is not None:
            if filter_.id:
                users = [u for u in users if u.id in filter_.id]
            if filter_.role:
                users = [u for u in users if u.role in filter_.role]

        if sort is not None and sort.sort_by is not None:
            reverse = sort.sort_by_order == SortByOrder.desc
            if sort.sort_by == "id":
                users.sort(reverse=reverse)
            elif sort.sort_by == "role":
                users.sort(key=lambda u: u.role.value, reverse=reverse)

        if pagination and pagination.limit is not None:
            offset = pagination.offset or 0
            limit = pagination.limit
            users = users[offset:offset + limit]

        for user in users:
            yield user

    async def create_user(
        self,
        data: UserCreate,
    ) -> User:
        user_id = data.id
        role = data.role
        agent = data.agent
        user_file = self._get_user_file_path(user_id)
        if user_file.exists():
            raise AlreadyExistsError(f"User {user_id} already exists")
        user = User(id=user_id, role=role, agent=agent)
        await self._write_user(user=user)
        return user

    async def update_users(
        self,
        filter_: UserFilter | None = None,
        *, data: UserUpdate,
    ) -> AsyncGenerator[User]:
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                parts = user_file.stem.split("_", 1)
                if len(parts) < 2:
                    continue
                user_id = uuid.UUID(parts[1])
            except ValueError:
                continue

            lock = await self._get_user_lock(user_id=user_id)
            async with lock:
                try:
                    async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                        content = await f.read()
                    user_data = UserData.model_validate_json(content)
                except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                    continue
                if filter_ is not None:
                    if filter_.id and user_data.id not in filter_.id:
                        continue
                    if filter_.role and user_data.role not in filter_.role:
                        continue
                if data.role is not None:
                    user_data.role = data.role
                if data.agent is not None:
                    user_data.agent = data.agent
                await self._write_user_data(user_data=user_data)
                yield user_data.to_user()

    async def delete_user(self, filter_: UserFilter) -> None:
        if not filter_.id:
            raise ValueError("delete_user requires filter_.id to be set")
        user_id = next(iter(filter_.id))
        lock = await self._get_user_lock(user_id=user_id)
        async with lock:
            user_file = self._get_user_file_path(user_id)
            if not user_file.exists():
                return

            user_file.unlink()
            for channel_file in self._settings.path.glob("channel_*.json"):
                try:
                    async with aiofiles.open(
                        channel_file, mode="r", encoding="utf-8"
                    ) as f:
                        content = await f.read()
                    channel_data = UserChannelData.model_validate_json(content)
                    if channel_data.user_id == user_id:
                        channel_file.unlink()
                except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                    continue

            for token_file in self._settings.path.glob("token_*.json"):
                try:
                    async with aiofiles.open(
                        token_file, mode="r", encoding="utf-8"
                    ) as f:
                        content = await f.read()
                    token_data = TokenData.model_validate_json(content)
                    if token_data.user_id == user_id:
                        token_file.unlink()
                except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                    continue

    async def delete_users(self, filter_: UserFilter | None = None) -> None:
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                user_data = UserData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue
            if filter_ is not None:
                if filter_.id and user_data.id not in filter_.id:
                    continue
                if filter_.role and user_data.role not in filter_.role:
                    continue
            await self.delete_user(filter_=UserFilter(id={user_data.id}))

    async def get_user_channel(
        self,
        filter_: UserChannelFilter,
        sort: BaseSort | None = None,
    ) -> UserChannel | None:
        async for channel in self.get_user_channels(filter_=filter_, pagination=BasePagination(limit=1, offset=0), sort=sort):
            return channel
        return None

    async def get_user_channels(
        self,
        filter_: UserChannelFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[UserChannel]:
        channels = []
        for channel_file in self._settings.path.glob("channel_*.json"):
            try:
                async with aiofiles.open(channel_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                channel_data = UserChannelData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue

            parts = channel_file.stem.split("_", 2)
            if len(parts) < 3:
                continue
            channel_key = parts[1]
            channel_internal_id = parts[2]

            actual_session_id = channel_data.sessions[-1] if channel_data.sessions else None
            channels.append(UserChannel(
                user_id=channel_data.user_id,
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
                actual_session_id=actual_session_id,
            ))

        if filter_ is not None:
            if filter_.user_id:
                channels = [c for c in channels if c.user_id in filter_.user_id]
            if filter_.channel_key:
                channels = [c for c in channels if c.channel_key in filter_.channel_key]
            if filter_.channel_internal_id:
                channels = [c for c in channels if c.channel_internal_id in filter_.channel_internal_id]
            if filter_.actual_session_id:
                channels = [c for c in channels if c.actual_session_id in filter_.actual_session_id]

        if sort is not None and sort.sort_by is not None:
            reverse = sort.sort_by_order == SortByOrder.desc
            if sort.sort_by == "user_id":
                channels.sort(key=lambda c: str(c.user_id), reverse=reverse)
            elif sort.sort_by == "channel_key":
                channels.sort(key=lambda c: c.channel_key, reverse=reverse)

        if pagination and pagination.limit is not None:
            offset = pagination.offset or 0
            limit = pagination.limit
            channels = channels[offset:offset + limit]

        for channel in channels:
            yield channel

    async def create_user_channel(self, data: UserChannelCreate) -> UserChannel:
        lock = await self._get_lock(
            channel_key=data.channel_key,
            channel_internal_id=data.channel_internal_id,
        )
        async with lock:
            existing = await self._read_channel(
                channel_key=data.channel_key,
                channel_internal_id=data.channel_internal_id,
            )
            if existing is not None and existing.user_id != data.user_id:
                raise AlreadyExistsError(
                    f"Channel {data.channel_key}/{data.channel_internal_id} already exists for user {existing.user_id}"
                )
            channel_data = UserChannelData(
                user_id=data.user_id,
                sessions=[data.actual_session_id] if data.actual_session_id else [],
            )
            await self._write_channel(
                channel_key=data.channel_key,
                channel_internal_id=data.channel_internal_id,
                data=channel_data,
            )
        return UserChannel(
            user_id=data.user_id,
            channel_key=data.channel_key,
            channel_internal_id=data.channel_internal_id,
            actual_session_id=data.actual_session_id,
        )

    async def update_user_channels(
        self,
        filter_: UserChannelFilter | None = None,
        *, data: UserChannelUpdate,
    ) -> AsyncGenerator[UserChannel]:
        for channel_file in self._settings.path.glob("channel_*.json"):
            parts = channel_file.stem.split("_", 2)
            if len(parts) < 3:
                continue
            channel_key = parts[1]
            channel_internal_id = parts[2]

            lock = await self._get_lock(
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
            )
            channel: UserChannel | None = None
            async with lock:
                try:
                    async with aiofiles.open(channel_file, mode="r", encoding="utf-8") as f:
                        content = await f.read()
                    channel_data = UserChannelData.model_validate_json(content)
                except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                    continue

                if filter_ is not None:
                    if filter_.user_id and channel_data.user_id not in filter_.user_id:
                        continue
                    if filter_.channel_key and channel_key not in filter_.channel_key:
                        continue
                    if filter_.channel_internal_id and channel_internal_id not in filter_.channel_internal_id:
                        continue

                new_channel_key = channel_key
                new_channel_internal_id = channel_internal_id
                if data.actual_session_id is not None:
                    channel_data.sessions = [data.actual_session_id]
                if data.channel_key is not None:
                    new_channel_key = data.channel_key
                if data.channel_internal_id is not None:
                    new_channel_internal_id = data.channel_internal_id

                await self._write_channel(
                    channel_key=new_channel_key,
                    channel_internal_id=new_channel_internal_id,
                    data=channel_data,
                )

                if new_channel_key != channel_key or new_channel_internal_id != channel_internal_id:
                    old_file = self._get_channel_file_path(channel_key, channel_internal_id)
                    if old_file.exists():
                        old_file.unlink()

                channel = UserChannel(
                    user_id=channel_data.user_id,
                    channel_key=new_channel_key,
                    channel_internal_id=new_channel_internal_id,
                    actual_session_id=channel_data.sessions[-1] if channel_data.sessions else None,
                )

            if channel is not None:
                yield channel

    async def delete_user_channel(self, filter_: UserChannelFilter) -> None:
        for channel_file in self._settings.path.glob("channel_*.json"):
            parts = channel_file.stem.split("_", 2)
            if len(parts) < 3:
                continue
            channel_key = parts[1]
            channel_internal_id = parts[2]

            lock = await self._get_lock(
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
            )
            async with lock:
                try:
                    async with aiofiles.open(channel_file, mode="r", encoding="utf-8") as f:
                        content = await f.read()
                    channel_data = UserChannelData.model_validate_json(content)
                except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                    continue

                if filter_.user_id and channel_data.user_id not in filter_.user_id:
                    continue
                if filter_.channel_key and channel_key not in filter_.channel_key:
                    continue
                if filter_.channel_internal_id and channel_internal_id not in filter_.channel_internal_id:
                    continue

                channel_file.unlink()

    async def delete_user_channels(self, filter_: UserChannelFilter | None = None) -> None:
        for channel_file in self._settings.path.glob("channel_*.json"):
            parts = channel_file.stem.split("_", 2)
            if len(parts) < 3:
                continue
            channel_key = parts[1]
            channel_internal_id = parts[2]

            lock = await self._get_lock(
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
            )
            async with lock:
                try:
                    async with aiofiles.open(channel_file, mode="r", encoding="utf-8") as f:
                        content = await f.read()
                    channel_data = UserChannelData.model_validate_json(content)
                except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                    continue

                if filter_ is not None:
                    if filter_.user_id and channel_data.user_id not in filter_.user_id:
                        continue
                    if filter_.channel_key and channel_key not in filter_.channel_key:
                        continue
                    if filter_.channel_internal_id and channel_internal_id not in filter_.channel_internal_id:
                        continue

                channel_file.unlink()

    async def get_cron(
        self,
        filter_: CronFilter,
        sort: BaseSort | None = None,
    ) -> CronTask | None:
        async for cron in self.get_crons(filter_=filter_, pagination=BasePagination(limit=1, offset=0), sort=sort):
            return cron
        return None

    async def get_crons(
        self,
        filter_: CronFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[CronTask]:
        crons = []
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                user_data = UserData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue

            for cron in user_data.crons:
                if filter_ is not None:
                    if filter_.id and cron.id not in filter_.id:
                        continue
                    if filter_.user_id and user_data.id not in filter_.user_id:
                        continue
                    if filter_.enabled is not None and cron.enabled != filter_.enabled:
                        continue
                crons.append(cron)

        if sort is not None and sort.sort_by is not None:
            reverse = sort.sort_by_order == SortByOrder.desc
            if sort.sort_by == "id":
                crons.sort(key=lambda c: c.id, reverse=reverse)

        if pagination and pagination.limit is not None:
            offset = pagination.offset or 0
            limit = pagination.limit
            crons = crons[offset:offset + limit]

        for cron in crons:
            yield cron

    async def create_cron(self, data: CronCreate) -> CronTask:
        lock = await self._get_user_lock(user_id=data.user_id)
        async with lock:
            user_data = await self._read_user_data(user_id=data.user_id)
            if user_data is None:
                user_data = UserData(
                    id=data.user_id, role=UserRoleEnum.USER, agent=None, crons=[]
                )
            cron = CronTask(
                id=data.id,
                user_id=data.user_id,
                path=data.path,
                cron=data.cron,
                enabled=data.enabled,
                args=data.args,
            )
            user_data.crons.append(cron)
            await self._write_user_data(user_data=user_data)
        return cron

    async def update_crons(
        self,
        filter_: CronFilter | None = None,
        *, data: CronUpdate,
    ) -> AsyncGenerator[CronTask]:
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                user_data = UserData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue
            updated = False
            yielded_crons: list[CronTask] = []
            for cron in user_data.crons:
                if filter_ is not None:
                    if filter_.id and cron.id not in filter_.id:
                        continue
                    if filter_.user_id and user_data.id not in filter_.user_id:
                        continue
                    if filter_.enabled is not None and cron.enabled != filter_.enabled:
                        continue
                if data.cron is not None:
                    cron.cron = data.cron
                if data.enabled is not None:
                    cron.enabled = data.enabled
                if data.args is not None:
                    cron.args = data.args
                updated = True
                yielded_crons.append(cron)
            if updated:
                lock = await self._get_user_lock(user_id=user_data.id)
                async with lock:
                    await self._write_user_data(user_data=user_data)
                for cron in yielded_crons:
                    yield cron

    async def delete_cron(self, filter_: CronFilter) -> None:
        cron_id = next(iter(filter_.id), None)
        if cron_id is None:
            return
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                user_data = UserData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue

            original_count = len(user_data.crons)
            user_data.crons = [c for c in user_data.crons if c.id != cron_id]

            if len(user_data.crons) != original_count:
                lock = await self._get_user_lock(user_id=user_data.id)
                async with lock:
                    await self._write_user_data(user_data=user_data)
                break

    async def delete_crons(self, filter_: CronFilter | None = None) -> None:
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                user_data = UserData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue
            original_count = len(user_data.crons)
            user_data.crons = [
                c
                for c in user_data.crons
                if not (
                    (filter_ is None)
                    or (filter_.id and c.id in filter_.id)
                    or (filter_.user_id and user_data.id in filter_.user_id)
                    or (filter_.enabled is not None and c.enabled == filter_.enabled)
                )
            ]
            if len(user_data.crons) != original_count:
                lock = await self._get_user_lock(user_id=user_data.id)
                async with lock:
                    await self._write_user_data(user_data=user_data)

    async def get_token(
        self,
        filter_: TokenFilter,
        sort: BaseSort | None = None,
    ) -> Token | None:
        async for token in self.get_tokens(filter_=filter_, pagination=BasePagination(limit=1, offset=0), sort=sort):
            return token
        return None

    async def get_tokens(
        self,
        filter_: TokenFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[Token]:
        tokens = []
        for token_file in self._settings.path.glob("token_*.json"):
            try:
                async with aiofiles.open(token_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                token_data = TokenData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue
            if filter_ is not None:
                if filter_.token and token_data.token not in filter_.token:
                    continue
                if filter_.user_id and token_data.user_id not in filter_.user_id:
                    continue
                if filter_.expires_at__gt is not None and (token_data.expires_at is None or token_data.expires_at <= filter_.expires_at__gt):
                    continue
                if filter_.expires_at__lt is not None and (token_data.expires_at is None or token_data.expires_at >= filter_.expires_at__lt):
                    continue
            tokens.append(Token(
                token=token_data.token,
                user_id=token_data.user_id,
                expires_at=token_data.expires_at,
            ))

        if sort is not None and sort.sort_by is not None:
            reverse = sort.sort_by_order == SortByOrder.desc
            if sort.sort_by == "token":
                tokens.sort(key=lambda t: t.token, reverse=reverse)

        if pagination and pagination.limit is not None:
            offset = pagination.offset or 0
            limit = pagination.limit
            tokens = tokens[offset:offset + limit]

        for token in tokens:
            yield token

    async def create_token(self, data: TokenCreate) -> Token:
        token = data.token
        if token is None:
            while True:
                token = secrets.token_urlsafe(32)
                old_token_data = await self._read_token(token=token)
                if old_token_data is None:
                    break
        else:
            old_token_data = await self._read_token(token=token)
            if old_token_data is not None:
                raise AlreadyExistsError(f"Token {token} already exists")

        token_data = TokenData(token=token, user_id=data.user_id, expires_at=data.expires_at)
        await self._write_token(token_data=token_data)
        return Token(token=token, user_id=data.user_id, expires_at=data.expires_at)

    async def update_tokens(
        self,
        filter_: TokenFilter | None = None,
        *, data: TokenUpdate,
    ) -> AsyncGenerator[Token]:
        for token_file in self._settings.path.glob("token_*.json"):
            try:
                async with aiofiles.open(token_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                token_data = TokenData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue
            if filter_ is not None:
                if filter_.token and token_data.token not in filter_.token:
                    continue
                if filter_.user_id and token_data.user_id not in filter_.user_id:
                    continue
            token_data.expires_at = data.expires_at
            await self._write_token(token_data=token_data)
            yield Token(
                token=token_data.token,
                user_id=token_data.user_id,
                expires_at=token_data.expires_at,
            )

    async def delete_token(self, filter_: TokenFilter) -> None:
        token_str = next(iter(filter_.token), None)
        if token_str is None:
            return
        token_file = self._get_token_file_path(token_str)
        if token_file.exists():
            token_file.unlink()

    async def delete_tokens(self, filter_: TokenFilter | None = None) -> None:
        for token_file in self._settings.path.glob("token_*.json"):
            try:
                async with aiofiles.open(token_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                token_data = TokenData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue
            if filter_ is not None:
                if filter_.token and token_data.token not in filter_.token:
                    continue
                if filter_.user_id and token_data.user_id not in filter_.user_id:
                    continue
            token_file.unlink()

    async def get_webhook(
        self,
        filter_: WebhookFilter,
        sort: BaseSort | None = None,
    ) -> Webhook | None:
        async for webhook in self.get_webhooks(filter_=filter_, pagination=BasePagination(limit=1, offset=0), sort=sort):
            return webhook
        return None

    async def get_webhooks(
        self,
        filter_: WebhookFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[Webhook]:
        webhooks = []
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                user_data = UserData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue

            for webhook in user_data.webhooks:
                if filter_ is not None:
                    if filter_.id and webhook.id not in filter_.id:
                        continue
                    if filter_.user_id and user_data.id not in filter_.user_id:
                        continue
                    if filter_.enabled is not None and webhook.enabled != filter_.enabled:
                        continue
                    if filter_.agent and webhook.agent not in filter_.agent:
                        continue
                    if filter_.channel and webhook.channel not in filter_.channel:
                        continue
                    if filter_.channel_internal_id and webhook.channel_internal_id not in filter_.channel_internal_id:
                        continue
                webhooks.append(webhook)

        if sort is not None and sort.sort_by is not None:
            reverse = sort.sort_by_order == SortByOrder.desc
            if sort.sort_by == "id":
                webhooks.sort(key=lambda w: w.id, reverse=reverse)

        if pagination and pagination.limit is not None:
            offset = pagination.offset or 0
            limit = pagination.limit
            webhooks = webhooks[offset:offset + limit]

        for webhook in webhooks:
            yield webhook

    async def create_webhook(self, data: WebhookCreate) -> Webhook:
        lock = await self._get_user_lock(user_id=data.user_id)
        async with lock:
            user_data = await self._read_user_data(user_id=data.user_id)
            if user_data is None:
                user_data = UserData(
                    id=data.user_id,
                    role=UserRoleEnum.USER,
                    agent=None,
                    crons=[],
                    webhooks=[],
                )
            webhook = Webhook(
                id=data.id,
                user_id=data.user_id,
                path=data.path,
                enabled=data.enabled,
                args=data.args,
                agent=data.agent,
                channel=data.channel,
                channel_internal_id=data.channel_internal_id,
            )
            user_data.webhooks.append(webhook)
            await self._write_user_data(user_data=user_data)
        return webhook

    async def update_webhooks(
        self,
        filter_: WebhookFilter | None = None,
        *, data: WebhookUpdate,
    ) -> AsyncGenerator[Webhook]:
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                user_data = UserData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue
            updated = False
            yielded_webhooks: list[Webhook] = []
            for webhook in user_data.webhooks:
                if filter_ is not None:
                    if filter_.id and webhook.id not in filter_.id:
                        continue
                    if filter_.user_id and user_data.id not in filter_.user_id:
                        continue
                    if filter_.enabled is not None and webhook.enabled != filter_.enabled:
                        continue
                    if filter_.agent and webhook.agent not in filter_.agent:
                        continue
                    if filter_.channel and webhook.channel not in filter_.channel:
                        continue
                    if filter_.channel_internal_id and webhook.channel_internal_id not in filter_.channel_internal_id:
                        continue
                if data.path is not None:
                    webhook.path = data.path
                if data.enabled is not None:
                    webhook.enabled = data.enabled
                if data.args is not None:
                    webhook.args = data.args
                if data.agent is not None:
                    webhook.agent = data.agent
                if data.channel is not None:
                    webhook.channel = data.channel
                if data.channel_internal_id is not None:
                    webhook.channel_internal_id = data.channel_internal_id
                updated = True
                yielded_webhooks.append(webhook)
            if updated:
                lock = await self._get_user_lock(user_id=user_data.id)
                async with lock:
                    await self._write_user_data(user_data=user_data)
                for webhook in yielded_webhooks:
                    yield webhook

    async def delete_webhook(self, filter_: WebhookFilter) -> None:
        webhook_id = next(iter(filter_.id), None)
        if webhook_id is None:
            return
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                user_data = UserData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue

            original_count = len(user_data.webhooks)
            user_data.webhooks = [w for w in user_data.webhooks if w.id != webhook_id]

            if len(user_data.webhooks) != original_count:
                lock = await self._get_user_lock(user_id=user_data.id)
                async with lock:
                    await self._write_user_data(user_data=user_data)
                break

    async def delete_webhooks(self, filter_: WebhookFilter | None = None) -> None:
        for user_file in self._settings.path.glob("user_*.json"):
            try:
                async with aiofiles.open(user_file, mode="r", encoding="utf-8") as f:
                    content = await f.read()
                user_data = UserData.model_validate_json(content)
            except (OSError, json.JSONDecodeError, pydantic.ValidationError):
                continue
            original_count = len(user_data.webhooks)
            user_data.webhooks = [
                w
                for w in user_data.webhooks
                if not (
                    (filter_ is None)
                    or (filter_.id and w.id in filter_.id)
                    or (filter_.user_id and user_data.id in filter_.user_id)
                    or (filter_.enabled is not None and w.enabled == filter_.enabled)
                    or (filter_.agent and w.agent in filter_.agent)
                    or (filter_.channel and w.channel in filter_.channel)
                    or (filter_.channel_internal_id and w.channel_internal_id in filter_.channel_internal_id)
                )
            ]
            if len(user_data.webhooks) != original_count:
                lock = await self._get_user_lock(user_id=user_data.id)
                async with lock:
                    await self._write_user_data(user_data=user_data)

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

    async def _get_user_lock(self, user_id: uuid.UUID) -> asyncio.Lock:
        lock_key = f"user_{user_id}"
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
