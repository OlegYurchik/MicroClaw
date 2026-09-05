from collections import defaultdict
from collections.abc import AsyncGenerator
import datetime
import secrets
import uuid

from .settings import MemoryUsersStorageSettings
from pydantic_filters import BaseSort, SortByOrder
from pydantic_filters.pagination import OffsetPagination as BasePagination

from microclaw.dto import CronTask, Token, User, UserChannel, UserChannelID, Webhook
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


class MemoryUsersStorage(UsersStorageInterface):
    def __init__(self, settings: MemoryUsersStorageSettings):
        self._settings = settings
        self._users: dict[uuid.UUID, User] = {}
        self._channels_users: dict[UserChannelID, uuid.UUID] = {}
        self._channel_sessions: defaultdict[UserChannelID, list[uuid.UUID]] = (
            defaultdict(list)
        )
        self._user_crons: dict[uuid.UUID, list[CronTask]] = defaultdict(list)
        self._user_webhooks: dict[uuid.UUID, list[Webhook]] = defaultdict(list)
        self._tokens: dict[str, tuple[uuid.UUID, datetime.datetime | None]] = {}
        self._tokens_by_user_id: dict[uuid.UUID, set[str]] = {}

    async def get_user(
        self,
        filter_: UserFilter,
        sort: BaseSort | None = None,
    ) -> User | None:
        user_id = next(iter(filter_.id), None)
        if user_id is None:
            return None
        return self._users.get(user_id)

    async def get_users(
        self,
        filter_: UserFilter | None = None,
        pagination: BasePagination | None = None,
        sort: BaseSort | None = None,
    ) -> AsyncGenerator[User]:
        users = list(self._users.values())

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
        if user_id in self._users:
            raise AlreadyExistsError(f"User {user_id} already exists")
        user = User(id=user_id, role=role, agent=agent)
        self._users[user_id] = user
        return user

    async def update_users(
        self,
        filter_: UserFilter | None = None,
        *, data: UserUpdate,
    ) -> AsyncGenerator[User]:
        for user in list(self._users.values()):
            if filter_ is not None:
                if filter_.id and user.id not in filter_.id:
                    continue
                if filter_.role and user.role not in filter_.role:
                    continue
            if data.role is not None:
                user.role = data.role
            if data.agent is not None:
                user.agent = data.agent
            yield user

    async def delete_user(self, filter_: UserFilter) -> None:
        if not filter_.id:
            raise ValueError("delete_user requires filter_.id to be set")
        user_id = next(iter(filter_.id))
        if user_id not in self._users:
            return

        del self._users[user_id]
        to_delete = [
            channel_id
            for channel_id, uid in self._channels_users.items()
            if uid == user_id
        ]
        for channel_id in to_delete:
            del self._channels_users[channel_id]
            if channel_id in self._channel_sessions:
                del self._channel_sessions[channel_id]

        if user_id in self._user_crons:
            del self._user_crons[user_id]

        if user_id in self._user_webhooks:
            del self._user_webhooks[user_id]

        to_delete_tokens = [
            token for token, (uid, _) in self._tokens.items() if uid == user_id
        ]
        for token in to_delete_tokens:
            del self._tokens[token]
        self._tokens_by_user_id.pop(user_id, None)

    async def delete_users(self, filter_: UserFilter | None = None) -> None:
        to_delete = []
        for user_id in list(self._users.keys()):
            user = self._users[user_id]
            if filter_ is not None:
                if filter_.id and user.id not in filter_.id:
                    continue
                if filter_.role and user.role not in filter_.role:
                    continue
            to_delete.append(user_id)
        for user_id in to_delete:
            await self.delete_user(filter_=UserFilter(id={user_id}))

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
        for user_channel_id, user_id in self._channels_users.items():
            if filter_ is not None:
                if filter_.user_id and user_id not in filter_.user_id:
                    continue
                if filter_.channel_key and user_channel_id.channel_key not in filter_.channel_key:
                    continue
                if filter_.channel_internal_id and user_channel_id.channel_internal_id not in filter_.channel_internal_id:
                    continue
            actual_session_id = None
            sessions = self._channel_sessions.get(user_channel_id)
            if sessions:
                actual_session_id = sessions[-1]
            if filter_ is not None and filter_.actual_session_id and actual_session_id not in filter_.actual_session_id:
                continue
            channels.append(UserChannel(
                user_id=user_id,
                channel_key=user_channel_id.channel_key,
                channel_internal_id=user_channel_id.channel_internal_id,
                actual_session_id=actual_session_id,
            ))

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
        user_channel_id = UserChannelID(
            channel_key=data.channel_key,
            channel_internal_id=data.channel_internal_id,
        )
        existing_user_id = self._channels_users.get(user_channel_id)
        if existing_user_id is not None and existing_user_id != data.user_id:
            raise AlreadyExistsError(
                f"Channel {data.channel_key}/{data.channel_internal_id} already exists for user {existing_user_id}"
            )
        self._channels_users[user_channel_id] = data.user_id
        if data.actual_session_id is not None:
            sessions = self._channel_sessions[user_channel_id]
            if data.actual_session_id not in sessions:
                sessions.append(data.actual_session_id)
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
        for user_channel_id in list(self._channels_users.keys()):
            user_id = self._channels_users[user_channel_id]
            if filter_ is not None:
                if filter_.user_id and user_id not in filter_.user_id:
                    continue
                if filter_.channel_key and user_channel_id.channel_key not in filter_.channel_key:
                    continue
                if filter_.channel_internal_id and user_channel_id.channel_internal_id not in filter_.channel_internal_id:
                    continue

            new_channel_id = user_channel_id
            if data.actual_session_id is not None:
                self._channel_sessions[user_channel_id] = [data.actual_session_id]
            if data.channel_key is not None or data.channel_internal_id is not None:
                new_channel_id = UserChannelID(
                    channel_key=data.channel_key if data.channel_key is not None else user_channel_id.channel_key,
                    channel_internal_id=data.channel_internal_id if data.channel_internal_id is not None else user_channel_id.channel_internal_id,
                )
                if new_channel_id != user_channel_id:
                    self._channels_users[new_channel_id] = user_id
                    del self._channels_users[user_channel_id]
                    sessions = self._channel_sessions.pop(user_channel_id, [])
                    self._channel_sessions[new_channel_id] = sessions

            yield UserChannel(
                user_id=user_id,
                channel_key=new_channel_id.channel_key,
                channel_internal_id=new_channel_id.channel_internal_id,
                actual_session_id=self._channel_sessions.get(new_channel_id, [None])[-1],
            )

    async def delete_user_channel(self, filter_: UserChannelFilter) -> None:
        to_delete = []
        for user_channel_id, user_id in list(self._channels_users.items()):
            if filter_.user_id and user_id not in filter_.user_id:
                continue
            if filter_.channel_key and user_channel_id.channel_key not in filter_.channel_key:
                continue
            if filter_.channel_internal_id and user_channel_id.channel_internal_id not in filter_.channel_internal_id:
                continue
            if filter_.actual_session_id:
                sessions = self._channel_sessions.get(user_channel_id, [])
                actual = sessions[-1] if sessions else None
                if actual not in filter_.actual_session_id:
                    continue
            to_delete.append(user_channel_id)
        for user_channel_id in to_delete:
            del self._channels_users[user_channel_id]
            self._channel_sessions.pop(user_channel_id, None)

    async def delete_user_channels(self, filter_: UserChannelFilter | None = None) -> None:
        to_delete = []
        for user_channel_id, user_id in list(self._channels_users.items()):
            if filter_ is not None:
                if filter_.user_id and user_id not in filter_.user_id:
                    continue
                if filter_.channel_key and user_channel_id.channel_key not in filter_.channel_key:
                    continue
                if filter_.channel_internal_id and user_channel_id.channel_internal_id not in filter_.channel_internal_id:
                    continue
            to_delete.append(user_channel_id)
        for user_channel_id in to_delete:
            del self._channels_users[user_channel_id]
            self._channel_sessions.pop(user_channel_id, None)

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
        for user_id, user_crons in self._user_crons.items():
            for cron in user_crons:
                if filter_ is not None:
                    if filter_.id and cron.id not in filter_.id:
                        continue
                    if filter_.user_id and user_id not in filter_.user_id:
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
        cron = CronTask(
            id=data.id,
            user_id=data.user_id,
            path=data.path,
            cron=data.cron,
            enabled=data.enabled,
            args=data.args,
        )
        self._user_crons[data.user_id].append(cron)
        return cron

    async def update_crons(
        self,
        filter_: CronFilter | None = None,
        *, data: CronUpdate,
    ) -> AsyncGenerator[CronTask]:
        for user_id, crons in list(self._user_crons.items()):
            for cron in crons:
                if filter_ is not None:
                    if filter_.id and cron.id not in filter_.id:
                        continue
                    if filter_.user_id and user_id not in filter_.user_id:
                        continue
                    if filter_.enabled is not None and cron.enabled != filter_.enabled:
                        continue
                if data.cron is not None:
                    cron.cron = data.cron
                if data.enabled is not None:
                    cron.enabled = data.enabled
                if data.args is not None:
                    cron.args = data.args
                yield cron

    async def delete_cron(self, filter_: CronFilter) -> None:
        cron_id = next(iter(filter_.id), None)
        if cron_id is None:
            return
        for user_id, crons in self._user_crons.items():
            self._user_crons[user_id] = [cron for cron in crons if cron.id != cron_id]

    async def delete_crons(self, filter_: CronFilter | None = None) -> None:
        for user_id, crons in list(self._user_crons.items()):
            self._user_crons[user_id] = [
                cron
                for cron in crons
                if not (
                    (filter_ is None)
                    or (filter_.id and cron.id in filter_.id)
                    or (filter_.user_id and user_id in filter_.user_id)
                    or (filter_.enabled is not None and cron.enabled == filter_.enabled)
                )
            ]

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
        for token, (user_id, expires_at) in self._tokens.items():
            if filter_ is not None:
                if filter_.token and token not in filter_.token:
                    continue
                if filter_.user_id and user_id not in filter_.user_id:
                    continue
                if filter_.expires_at__gt is not None and (expires_at is None or expires_at <= filter_.expires_at__gt):
                    continue
                if filter_.expires_at__lt is not None and (expires_at is None or expires_at >= filter_.expires_at__lt):
                    continue
            tokens.append(Token(token=token, user_id=user_id, expires_at=expires_at))

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
        expires_at = data.expires_at
        token = data.token
        if token is None:
            while True:
                token = secrets.token_urlsafe(32)
                if token not in self._tokens:
                    break
        elif token in self._tokens:
            raise AlreadyExistsError(f"Token {token} already exists")
        self._tokens[token] = (data.user_id, expires_at)
        self._tokens_by_user_id.setdefault(data.user_id, set()).add(token)
        return Token(token=token, user_id=data.user_id, expires_at=expires_at)

    async def update_tokens(
        self,
        filter_: TokenFilter | None = None,
        *, data: TokenUpdate,
    ) -> AsyncGenerator[Token]:
        tokens_to_check = list(self._tokens.items())
        if filter_ is not None and filter_.user_id:
            tokens_to_check = [
                (token, self._tokens[token])
                for uid in filter_.user_id
                for token in self._tokens_by_user_id.get(uid, set())
                if token in self._tokens
            ]
        for token, (user_id, _) in tokens_to_check:
            if filter_ is not None:
                if filter_.token and token not in filter_.token:
                    continue
            self._tokens[token] = (user_id, data.expires_at)
            self._tokens_by_user_id.setdefault(user_id, set()).add(token)
            yield Token(token=token, user_id=user_id, expires_at=data.expires_at)

    async def delete_token(self, filter_: TokenFilter) -> None:
        token_str = next(iter(filter_.token), None)
        if token_str is None:
            return
        user_id, _ = self._tokens.pop(token_str, (None, None))
        if user_id is not None:
            self._tokens_by_user_id.get(user_id, set()).discard(token_str)

    async def delete_tokens(self, filter_: TokenFilter | None = None) -> None:
        to_delete = []
        tokens_to_check = list(self._tokens.items())
        if filter_ is not None and filter_.user_id:
            tokens_to_check = [
                (token, self._tokens[token])
                for uid in filter_.user_id
                for token in self._tokens_by_user_id.get(uid, set())
                if token in self._tokens
            ]
        for token, (user_id, _) in tokens_to_check:
            if filter_ is not None:
                if filter_.token and token not in filter_.token:
                    continue
            to_delete.append(token)
        for token in to_delete:
            user_id, _ = self._tokens.pop(token, (None, None))
            if user_id is not None:
                self._tokens_by_user_id.get(user_id, set()).discard(token)

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
        for user_id, user_webhooks in self._user_webhooks.items():
            for webhook in user_webhooks:
                if filter_ is not None:
                    if filter_.id and webhook.id not in filter_.id:
                        continue
                    if filter_.user_id and user_id not in filter_.user_id:
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
        self._user_webhooks[data.user_id].append(webhook)
        return webhook

    async def update_webhooks(
        self,
        filter_: WebhookFilter | None = None,
        *, data: WebhookUpdate,
    ) -> AsyncGenerator[Webhook]:
        for user_id, webhooks in list(self._user_webhooks.items()):
            for webhook in webhooks:
                if filter_ is not None:
                    if filter_.id and webhook.id not in filter_.id:
                        continue
                    if filter_.user_id and user_id not in filter_.user_id:
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
                yield webhook

    async def delete_webhook(self, filter_: WebhookFilter) -> None:
        webhook_id = next(iter(filter_.id), None)
        if webhook_id is None:
            return
        for user_id, webhooks in self._user_webhooks.items():
            self._user_webhooks[user_id] = [
                w for w in webhooks if w.id != webhook_id
            ]

    async def delete_webhooks(self, filter_: WebhookFilter | None = None) -> None:
        for user_id, webhooks in list(self._user_webhooks.items()):
            self._user_webhooks[user_id] = [
                w
                for w in webhooks
                if not (
                    (filter_ is None)
                    or (filter_.id and w.id in filter_.id)
                    or (filter_.user_id and user_id in filter_.user_id)
                    or (filter_.enabled is not None and w.enabled == filter_.enabled)
                    or (filter_.agent and w.agent in filter_.agent)
                    or (filter_.channel and w.channel in filter_.channel)
                    or (filter_.channel_internal_id and w.channel_internal_id in filter_.channel_internal_id)
                )
            ]
