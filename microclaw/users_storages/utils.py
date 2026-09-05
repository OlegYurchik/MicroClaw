import datetime
import secrets
import uuid

from microclaw.dto import Token, User
from microclaw.users_storages.dto import (
    TokenCreate,
    UserChannelCreate,
    UserChannelUpdate,
)
from microclaw.users_storages.filters import TokenFilter, UserChannelFilter
from microclaw.users_storages.interfaces import UsersStorageInterface
from microclaw.utils import utcnow


async def get_user_by_session(
    storage: UsersStorageInterface,
    session_id: uuid.UUID,
) -> User | None:
    from microclaw.users_storages.filters import UserFilter

    async for channel in storage.get_user_channels(
        filter_=UserChannelFilter(actual_session_id={session_id})
    ):
        user = await storage.get_user(filter_=UserFilter(id={channel.user_id}))
        return user
    return None


async def get_user_by_token(
    storage: UsersStorageInterface,
    token: str,
) -> User | None:
    from microclaw.users_storages.filters import UserFilter

    token_info = await storage.get_token(filter_=TokenFilter(token={token}))
    if token_info is None:
        return None
    if not token_info.is_valid():
        return None
    return await storage.get_user(filter_=UserFilter(id={token_info.user_id}))


async def get_user_by_channel(
    storage: UsersStorageInterface,
    channel_key: str,
    channel_internal_id: str,
) -> User | None:
    from microclaw.users_storages.filters import UserFilter

    async for channel in storage.get_user_channels(
        filter_=UserChannelFilter(
            channel_key={channel_key},
            channel_internal_id={channel_internal_id},
        )
    ):
        return await storage.get_user(filter_=UserFilter(id={channel.user_id}))
    return None


async def get_actual_session(
    storage: UsersStorageInterface,
    user_id: uuid.UUID,
    channel_key: str,
    channel_internal_id: str,
) -> uuid.UUID | None:
    async for channel in storage.get_user_channels(
        filter_=UserChannelFilter(
            user_id={user_id},
            channel_key={channel_key},
            channel_internal_id={channel_internal_id},
        )
    ):
        return channel.actual_session_id
    return None


async def get_user_sessions(
    storage: UsersStorageInterface,
    user_id: uuid.UUID,
    channel_key: str,
    channel_internal_id: str,
) -> list[uuid.UUID]:
    sessions = []
    async for channel in storage.get_user_channels(
        filter_=UserChannelFilter(
            user_id={user_id},
            channel_key={channel_key},
            channel_internal_id={channel_internal_id},
        )
    ):
        if channel.actual_session_id is not None:
            sessions.append(channel.actual_session_id)
    return sessions


async def attach_session_to_user(
    storage: UsersStorageInterface,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    channel_key: str,
    channel_internal_id: str,
) -> None:
    filter_ = UserChannelFilter(
        user_id={user_id},
        channel_key={channel_key},
        channel_internal_id={channel_internal_id},
    )
    channels = [
        channel async for channel in storage.get_user_channels(filter_=filter_)
    ]
    if channels:
        async for _ in storage.update_user_channels(
            filter_=filter_,
            data=UserChannelUpdate(actual_session_id=session_id),
        ):
            pass
    else:
        await storage.create_user_channel(
            data=UserChannelCreate(
                user_id=user_id,
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
                actual_session_id=session_id,
            )
        )


async def create_token_for_user(
    storage: UsersStorageInterface,
    user_id: uuid.UUID,
    ttl: datetime.timedelta | None = datetime.timedelta(days=30),
) -> Token:
    expires_at = None
    if ttl is not None:
        expires_at = utcnow() + ttl
    while True:
        token = secrets.token_urlsafe(32)
        existing = await storage.get_token(filter_=TokenFilter(token={token}))
        if existing is None:
            break
    return await storage.create_token(
        data=TokenCreate(token=token, user_id=user_id, expires_at=expires_at)
    )
