import uuid

import fastapi

from microclaw.api.rest.dependencies import users_storage
from microclaw.api.rest.exceptions import HTTPNotFound
from microclaw.dto import User
from microclaw.users_storages import UsersStorageInterface


async def user(
        users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
        user_id: uuid.UUID = fastapi.Path(),
) -> User:
    user = await users_storage.get_user(user_id=user_id)
    if user is None:
        raise HTTPNotFound()
    return user
