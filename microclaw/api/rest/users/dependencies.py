import uuid

import fastapi

from microclaw.api.rest.dependencies import auth, users_storage
from microclaw.api.rest.exceptions import HTTPForbidden, HTTPNotFound
from microclaw.dto import User, UserRoleEnum
from microclaw.users_storages import UsersStorageInterface
from microclaw.users_storages.filters import UserFilter


async def user(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    user_id: uuid.UUID = fastapi.Path(),
) -> User:
    user = await users_storage.get_user(
        filter_=UserFilter(id={user_id})
    )
    if user is None:
        raise HTTPNotFound()
    return user


async def is_admin_or_self(
    current_user: User = fastapi.Depends(auth),
    target_user: User = fastapi.Depends(user),
) -> User:
    if current_user.role != UserRoleEnum.ADMIN and current_user.id != target_user.id:
        raise HTTPForbidden()
    return current_user
