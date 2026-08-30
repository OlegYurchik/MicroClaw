import uuid

import fastapi

from microclaw.api.rest.dependencies import (
    auth,
)
from microclaw.api.rest.dependencies import (
    sessions_storage as sessions_storage_dep,
)
from microclaw.api.rest.dependencies import (
    users_storage as users_storage_dep,
)
from microclaw.api.rest.exceptions import HTTPForbidden, HTTPNotFound
from microclaw.dto import SessionMetadata, User, UserRoleEnum
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.users_storages import UsersStorageInterface


async def is_session_owner(
    session_id: uuid.UUID = fastapi.Path(),
    sessions_storage: SessionsStorageInterface = fastapi.Depends(sessions_storage_dep),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dep),
    current_user: User = fastapi.Depends(auth),
) -> SessionMetadata:
    meta = await sessions_storage.get_session(session_id)
    if meta is None:
        raise HTTPNotFound()
    if current_user.role != UserRoleEnum.ADMIN:
        owner = await users_storage.get_user_by_session(session_id)
        if owner is None or owner.id != current_user.id:
            raise HTTPForbidden()
    return meta
