from collections.abc import AsyncGenerator

from .filters import (
    CronFilter,
    TokenFilter,
    UserChannelFilter,
    UserFilter,
    WebhookFilter,
)
import facet
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


class UsersStorageInterface(facet.AsyncioServiceMixin):
    """Users storage interface.

    .. note::
        ``None`` values in update DTOs (e.g. ``UserUpdate``, ``CronUpdate``)
        mean "do not update" rather than "set to null". To clear a field,
        callers must use an explicit sentinel or a dedicated clear method.
    """

    # Users
    async def get_user(
        self,
        filter_: UserFilter,
        sort: BaseSort | None = None,
    ) -> User | None:
        raise NotImplementedError

    async def get_users(
        self,
        filter_: UserFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[User]:
        raise NotImplementedError

    async def create_user(
        self,
        data: UserCreate,
    ) -> User:
        raise NotImplementedError

    async def update_users(
        self,
        filter_: UserFilter | None = None,
        *, data: UserUpdate,
    ) -> AsyncGenerator[User]:
        raise NotImplementedError

    async def update_user(
        self,
        filter_: UserFilter,
        *, data: UserUpdate,
    ) -> User | None:
        async for user in self.update_users(filter_=filter_, data=data):
            return user
        return None

    async def delete_user(self, filter_: UserFilter) -> None:
        raise NotImplementedError

    async def delete_users(self, filter_: UserFilter | None = None) -> None:
        raise NotImplementedError

    # User channels
    async def get_user_channel(
        self,
        filter_: UserChannelFilter,
        sort: BaseSort | None = None,
    ) -> UserChannel | None:
        raise NotImplementedError

    async def get_user_channels(
        self,
        filter_: UserChannelFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[UserChannel]:
        raise NotImplementedError

    async def create_user_channel(
        self,
        data: UserChannelCreate,
    ) -> UserChannel:
        raise NotImplementedError

    async def update_user_channels(
        self,
        filter_: UserChannelFilter | None = None,
        *, data: UserChannelUpdate,
    ) -> AsyncGenerator[UserChannel]:
        raise NotImplementedError

    async def update_user_channel(
        self,
        filter_: UserChannelFilter,
        *, data: UserChannelUpdate,
    ) -> UserChannel | None:
        async for channel in self.update_user_channels(filter_=filter_, data=data):
            return channel
        return None

    async def delete_user_channel(self, filter_: UserChannelFilter) -> None:
        raise NotImplementedError

    async def delete_user_channels(
        self,
        filter_: UserChannelFilter | None = None,
    ) -> None:
        raise NotImplementedError

    # Crons
    async def get_cron(
        self,
        filter_: CronFilter,
        sort: BaseSort | None = None,
    ) -> CronTask | None:
        raise NotImplementedError

    async def get_crons(
        self,
        filter_: CronFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[CronTask]:
        raise NotImplementedError

    async def create_cron(
        self,
        data: CronCreate,
    ) -> CronTask:
        raise NotImplementedError

    async def update_crons(
        self,
        filter_: CronFilter | None = None,
        *, data: CronUpdate,
    ) -> AsyncGenerator[CronTask]:
        raise NotImplementedError

    async def update_cron(
        self,
        filter_: CronFilter,
        *, data: CronUpdate,
    ) -> CronTask | None:
        async for cron in self.update_crons(filter_=filter_, data=data):
            return cron
        return None

    async def delete_cron(self, filter_: CronFilter) -> None:
        raise NotImplementedError

    async def delete_crons(self, filter_: CronFilter | None = None) -> None:
        raise NotImplementedError

    # Tokens
    async def get_token(
        self,
        filter_: TokenFilter,
        sort: BaseSort | None = None,
    ) -> Token | None:
        raise NotImplementedError

    async def get_tokens(
        self,
        filter_: TokenFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[Token]:
        raise NotImplementedError

    async def create_token(
        self,
        data: TokenCreate,
    ) -> Token:
        raise NotImplementedError

    async def update_tokens(
        self,
        filter_: TokenFilter | None = None,
        *, data: TokenUpdate,
    ) -> AsyncGenerator[Token]:
        raise NotImplementedError

    async def update_token(
        self,
        filter_: TokenFilter,
        *, data: TokenUpdate,
    ) -> Token | None:
        async for token in self.update_tokens(filter_=filter_, data=data):
            return token
        return None

    async def delete_token(self, filter_: TokenFilter) -> None:
        raise NotImplementedError

    async def delete_tokens(self, filter_: TokenFilter | None = None) -> None:
        raise NotImplementedError

    # Webhooks
    async def get_webhook(
        self,
        filter_: WebhookFilter,
        sort: BaseSort | None = None,
    ) -> Webhook | None:
        raise NotImplementedError

    async def get_webhooks(
        self,
        filter_: WebhookFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[Webhook]:
        raise NotImplementedError

    async def create_webhook(
        self,
        data: WebhookCreate,
    ) -> Webhook:
        raise NotImplementedError

    async def update_webhooks(
        self,
        filter_: WebhookFilter | None = None,
        *, data: WebhookUpdate,
    ) -> AsyncGenerator[Webhook]:
        raise NotImplementedError

    async def update_webhook(
        self,
        filter_: WebhookFilter,
        *, data: WebhookUpdate,
    ) -> Webhook | None:
        async for webhook in self.update_webhooks(filter_=filter_, data=data):
            return webhook
        return None

    async def delete_webhook(self, filter_: WebhookFilter) -> None:
        raise NotImplementedError

    async def delete_webhooks(self, filter_: WebhookFilter | None = None) -> None:
        raise NotImplementedError
