import datetime

from .dependencies import is_admin_or_self
from .dependencies import user as user_dependency
from .schemas import (
    TokenCreateRequest,
    UserCreateRequest,
    UserListResponse,
    UserSessionsResponse,
    UserUpdateRequest,
)
import fastapi

from microclaw.api.rest.dependencies import is_admin, list_query_params, users_storage
from microclaw.api.rest.exceptions import HTTPNotFound
from microclaw.api.rest.schemas import ListQueryParams, TokenResponse, UserResponse
from microclaw.dto import User
from microclaw.users_storages import UsersStorageInterface
from microclaw.users_storages.filters import UserFilter
from microclaw.utils import Empty


async def list_users(
    role: str | None = fastapi.Query(default=None),
    params: ListQueryParams = fastapi.Depends(list_query_params),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin),
) -> UserListResponse:
    filter_ = UserFilter(role=role)

    users = [
        user async for user in users_storage.get_users(
            filter=filter_, pagination=params.get_pagination(), sort=params.get_sort()
        )
    ]
    response = UserListResponse.from_items(items=users)
    if len(users) == params.limit:
        response.next_cursor = params.next_cursor(len(users))
    return response


async def create_user(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin),
    user_create_request: UserCreateRequest = fastapi.Body(embed=False),
) -> UserResponse:
    user = await users_storage.create_user(
        role=user_create_request.role,
        agent_settings=user_create_request.agent,
    )
    return UserResponse.from_item(item=user)


async def get_user(
    _: User = fastapi.Depends(is_admin_or_self),
    target_user: User = fastapi.Depends(user_dependency),
) -> UserResponse:
    return UserResponse.from_item(item=target_user)


async def update_user(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin_or_self),
    target_user: User = fastapi.Depends(user_dependency),
    user_update_request: UserUpdateRequest = fastapi.Body(embed=False),
) -> UserResponse:
    update_data = user_update_request.model_dump(exclude_unset=True)
    updated = await users_storage.update_user(
        user_id=target_user.id,
        role=update_data.get("role", Empty),
        agent_settings=update_data.get("agent", Empty),
    )
    return UserResponse.from_item(item=updated)


async def delete_user(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin),
    target_user: User = fastapi.Depends(user_dependency),
) -> None:
    await users_storage.delete_user(user_id=target_user.id)


async def list_user_sessions(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin_or_self),
    target_user: User = fastapi.Depends(user_dependency),
) -> UserSessionsResponse:
    sessions = await users_storage.get_user_sessions(
        user_id=target_user.id,
        channel_key="rest",
        channel_internal_id=str(target_user.id),
    )
    return UserSessionsResponse.from_items(items=sessions)


async def create_user_token(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin_or_self),
    target_user: User = fastapi.Depends(user_dependency),
    token_create_request: TokenCreateRequest = fastapi.Body(embed=False),
) -> TokenResponse:
    ttl = (
        datetime.timedelta(days=token_create_request.ttl_days)
        if token_create_request.ttl_days is not None
        else None
    )
    token_info = await users_storage.create_token_for_user(
        user_id=target_user.id, ttl=ttl
    )
    return TokenResponse(token=token_info.token, expires_at=token_info.expires_at)


async def delete_user_token(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin_or_self),
    target_user: User = fastapi.Depends(user_dependency),
    token: str = fastapi.Path(),
) -> None:
    token_owner = await users_storage.get_user_by_token(token=token)
    if token_owner is None or token_owner.id != target_user.id:
        raise HTTPNotFound()
    await users_storage.delete_token(token=token)
