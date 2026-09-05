import uuid

import fastapi

from microclaw.api.rest.dependencies import auth
from microclaw.api.rest.dependencies import (
    sessions_storage as sessions_storage_dep,
)
from microclaw.api.rest.dependencies import (
    users_storage as users_storage_dep,
)
from microclaw.api.rest.exceptions import HTTPForbidden, HTTPNotFound
from microclaw.dto import Session, User, UserRoleEnum
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.sessions_storages.filters import SessionFilter
from microclaw.users_storages import UsersStorageInterface
from microclaw.users_storages.filters import UserChannelFilter


async def is_session_owner(
    session_id: uuid.UUID = fastapi.Path(),
    sessions_storage: SessionsStorageInterface = fastapi.Depends(sessions_storage_dep),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dep),
    current_user: User = fastapi.Depends(auth),
) -> Session:
    meta = await sessions_storage.get_session(
        filter_=SessionFilter(id={session_id})
    )
    if meta is None:
        raise HTTPNotFound()
    if current_user.role != UserRoleEnum.ADMIN:
        owner_ids = set()
        async for channel in users_storage.get_user_channels(
            filter_=UserChannelFilter(actual_session_id={session_id})
        ):
            if channel.user_id is not None:
                owner_ids.add(channel.user_id)
        if current_user.id not in owner_ids:
            raise HTTPForbidden()
    return meta
