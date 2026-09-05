from collections.abc import AsyncGenerator
import datetime
import secrets

from .repositories import (
    CronsRepository,
    TokensRepository,
    UserChannelsRepository,
    UsersRepository,
    WebhooksRepository,
)
from .settings import DatabaseUsersStorageSettings
from .tables import UserTable
import facet
from metaorm import RepositoriesContainer
from pydantic_filters import BaseSort
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.dto import CronTask, Token, User, UserChannel, Webhook
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
from microclaw.users_storages.filters import (
    CronFilter,
    TokenFilter,
    UserChannelFilter,
    UserFilter,
    WebhookFilter,
)
from microclaw.users_storages.interfaces import UsersStorageInterface


class DatabaseUsersStorage(UsersStorageInterface, facet.AsyncioServiceMixin):
    def __init__(self, settings: DatabaseUsersStorageSettings):
        self._settings = settings
        self._container = RepositoriesContainer(settings=settings)
        self._users_repository = self._container.get_repository(UsersRepository)
        self._channels_repository = self._container.get_repository(UserChannelsRepository)
        self._crons_repository = self._container.get_repository(CronsRepository)
        self._tokens_repository = self._container.get_repository(TokensRepository)
        self._webhooks_repository = self._container.get_repository(WebhooksRepository)

    async def start(self):
        async with self._container.engine.begin() as conn:
            await conn.run_sync(UserTable.metadata.create_all)

    async def stop(self):
        await self._container.engine.dispose()

    async def get_user(
        self,
        filter_: UserFilter,
        sort: BaseSort | None = None,
    ) -> User | None:
        return await self._users_repository.get_item(filter_=filter_, sort=sort)

    async def get_users(
        self,
        filter_: UserFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[User]:
        async for user in self._users_repository.get_items(
            filter_=filter_, pagination=pagination, sort=sort
        ):
            yield user

    async def create_user(
        self,
        data: UserCreate,
    ) -> User:
        from metaorm import AlreadyExistsError as MetaormAlreadyExistsError

        from microclaw.users_storages.exceptions import AlreadyExistsError

        user_id = data.id
        role = data.role
        agent = data.agent
        try:
            return await self._users_repository.create_item(
                User(id=user_id, role=role, agent=agent)
            )
        except MetaormAlreadyExistsError as exc:
            raise AlreadyExistsError(f"User {user_id} already exists") from exc

    async def update_users(
        self,
        filter_: UserFilter | None = None,
        *, data: UserUpdate,
    ) -> AsyncGenerator[User]:
        values = {}
        if data.role is not None:
            values["role"] = data.role
        if data.agent is not None:
            values["agent"] = data.agent
        async for item in self._users_repository.update_items(filter_=filter_, **values):
            yield item

    async def delete_user(self, filter_: UserFilter) -> None:
        await self._users_repository.delete_items(filter_=filter_)

    async def delete_users(self, filter_: UserFilter | None = None) -> None:
        await self._users_repository.delete_items(filter_=filter_)

    async def get_user_channel(
        self,
        filter_: UserChannelFilter,
        sort: BaseSort | None = None,
    ) -> UserChannel | None:
        return await self._channels_repository.get_item(filter_=filter_, sort=sort)

    async def get_user_channels(
        self,
        filter_: UserChannelFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[UserChannel]:
        async for channel in self._channels_repository.get_items(
            filter_=filter_, pagination=pagination, sort=sort
        ):
            yield channel

    async def create_user_channel(
        self,
        data: UserChannelCreate,
    ) -> UserChannel:
        user_channel = UserChannel(
            user_id=data.user_id,
            channel_key=data.channel_key,
            channel_internal_id=data.channel_internal_id,
            actual_session_id=data.actual_session_id,
        )
        return await self._channels_repository.create_item(user_channel)

    async def update_user_channels(
        self,
        filter_: UserChannelFilter | None = None,
        *, data: UserChannelUpdate,
    ) -> AsyncGenerator[UserChannel]:
        values = {}
        if data.actual_session_id is not None:
            values["actual_session_id"] = data.actual_session_id
        if data.channel_key is not None:
            values["channel_key"] = data.channel_key
        if data.channel_internal_id is not None:
            values["channel_internal_id"] = data.channel_internal_id
        async for item in self._channels_repository.update_items(filter_=filter_, **values):
            yield item

    async def delete_user_channel(self, filter_: UserChannelFilter) -> None:
        await self._channels_repository.delete_items(filter_=filter_)

    async def delete_user_channels(self, filter_: UserChannelFilter | None = None) -> None:
        await self._channels_repository.delete_items(filter_=filter_)

    async def get_cron(
        self,
        filter_: CronFilter,
        sort: BaseSort | None = None,
    ) -> CronTask | None:
        return await self._crons_repository.get_item(filter_=filter_, sort=sort)

    async def get_crons(
        self,
        filter_: CronFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[CronTask]:
        async for cron in self._crons_repository.get_items(
            filter_=filter_, pagination=pagination, sort=sort
        ):
            yield cron

    async def create_cron(self, data: CronCreate) -> CronTask:
        return await self._crons_repository.create_item(
            CronTask(
                id=data.id,
                user_id=data.user_id,
                path=data.path,
                cron=data.cron,
                enabled=data.enabled,
                args=data.args,
            )
        )

    async def update_crons(
        self,
        filter_: CronFilter | None = None,
        *, data: CronUpdate,
    ) -> AsyncGenerator[CronTask]:
        values = {}
        if data.cron is not None:
            values["cron"] = data.cron
        if data.enabled is not None:
            values["enabled"] = data.enabled
        if data.args is not None:
            values["args"] = data.args
        async for item in self._crons_repository.update_items(filter_=filter_, **values):
            yield item

    async def delete_cron(self, filter_: CronFilter) -> None:
        await self._crons_repository.delete_items(filter_=filter_)

    async def delete_crons(self, filter_: CronFilter | None = None) -> None:
        await self._crons_repository.delete_items(filter_=filter_)

    async def get_token(
        self,
        filter_: TokenFilter,
        sort: BaseSort | None = None,
    ) -> Token | None:
        return await self._tokens_repository.get_item(filter_=filter_, sort=sort)

    async def get_tokens(
        self,
        filter_: TokenFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[Token]:
        async for token in self._tokens_repository.get_items(
            filter_=filter_, pagination=pagination, sort=sort
        ):
            yield token

    async def create_token(self, data: TokenCreate) -> Token:
        from metaorm import AlreadyExistsError as MetaormAlreadyExistsError

        from microclaw.users_storages.exceptions import AlreadyExistsError

        token = data.token
        if token is None:
            token = secrets.token_urlsafe(32)

        expires_at = data.expires_at
        if expires_at is not None and expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(datetime.timezone.utc)

        try:
            token_info = await self._tokens_repository.create_item(
                Token(token=token, user_id=data.user_id, expires_at=expires_at)
            )
        except MetaormAlreadyExistsError as exc:
            raise AlreadyExistsError(f"Token {token} already exists") from exc
        return token_info

    async def update_tokens(
        self,
        filter_: TokenFilter | None = None,
        *, data: TokenUpdate,
    ) -> AsyncGenerator[Token]:
        expires_at = data.expires_at
        if expires_at is not None and expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(datetime.timezone.utc)
        async for item in self._tokens_repository.update_items(
            filter_=filter_, expires_at=expires_at
        ):
            yield item

    async def delete_token(self, filter_: TokenFilter) -> None:
        await self._tokens_repository.delete_items(filter_=filter_)

    async def delete_tokens(self, filter_: TokenFilter | None = None) -> None:
        await self._tokens_repository.delete_items(filter_=filter_)

    async def get_webhook(
        self,
        filter_: WebhookFilter,
        sort: BaseSort | None = None,
    ) -> Webhook | None:
        return await self._webhooks_repository.get_item(filter_=filter_, sort=sort)

    async def get_webhooks(
        self,
        filter_: WebhookFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[Webhook]:
        async for webhook in self._webhooks_repository.get_items(
            filter_=filter_, pagination=pagination, sort=sort
        ):
            yield webhook

    async def create_webhook(self, data: WebhookCreate) -> Webhook:
        return await self._webhooks_repository.create_item(
            Webhook(
                id=data.id,
                user_id=data.user_id,
                path=data.path,
                enabled=data.enabled,
                args=data.args,
                agent=data.agent,
                channel=data.channel,
                channel_internal_id=data.channel_internal_id,
            )
        )

    async def update_webhooks(
        self,
        filter_: WebhookFilter | None = None,
        *, data: WebhookUpdate,
    ) -> AsyncGenerator[Webhook]:
        values = {}
        if data.path is not None:
            values["path"] = data.path
        if data.enabled is not None:
            values["enabled"] = data.enabled
        if data.args is not None:
            values["args"] = data.args
        if data.agent is not None:
            values["agent"] = data.agent
        if data.channel is not None:
            values["channel"] = data.channel
        if data.channel_internal_id is not None:
            values["channel_internal_id"] = data.channel_internal_id
        async for item in self._webhooks_repository.update_items(filter_=filter_, **values):
            yield item

    async def delete_webhook(self, filter_: WebhookFilter) -> None:
        await self._webhooks_repository.delete_items(filter_=filter_)

    async def delete_webhooks(self, filter_: WebhookFilter | None = None) -> None:
        await self._webhooks_repository.delete_items(filter_=filter_)
