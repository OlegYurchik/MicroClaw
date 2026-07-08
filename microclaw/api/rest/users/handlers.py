import fastapi

from microclaw.api.rest.dependencies import is_admin, users_storage
from microclaw.dto import User
from microclaw.users_storages import UsersStorageInterface
from .dependencies import user
from .schemas import (
    UserCreateRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)


async def list_users(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin),
) -> UserListResponse:
    users = [user async for user in users_storage.get_users()]
    return UserListResponse.from_items(items=users)


async def create_user(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin),
    user_create_request: UserCreateRequest = fastapi.Body(embed=False),
) -> UserResponse:
    user = await users_storage.create_user(
        user_id=user_create_request.id,
        role=user_create_request.role,
        agent_settings=user_create_request.agent,
    )
    return UserResponse.from_item(item=user)


async def get_user(
    _: User = fastapi.Depends(is_admin),
    user: User = fastapi.Depends(user),
) -> UserResponse:
    return UserResponse.from_item(item=user)


async def update_user(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin),
    user: User = fastapi.Depends(user),
    user_update_request: UserUpdateRequest = fastapi.Body(embed=False),
) -> UserResponse:
    user = await users_storage.update_user(
        user_id=user.id, role=user.role, agent=user.agent
    )
    return UserResponse.from_item(item=user)


async def delete_user(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin),
    user: User = fastapi.Depends(user),
) -> fastapi.Response:
    await users_storage.delete_user(user_id=user.id)
