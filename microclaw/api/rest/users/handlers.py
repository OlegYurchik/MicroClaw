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
from microclaw.users_storages.dto import TokenCreate, UserCreate, UserUpdate
from microclaw.users_storages.filters import TokenFilter, UserChannelFilter, UserFilter
from microclaw.utils import utcnow


async def list_users(
    role: str | None = fastapi.Query(default=None),
    params: ListQueryParams = fastapi.Depends(list_query_params),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin),
) -> UserListResponse:
    filter_ = UserFilter(role={role}) if role else UserFilter()

    users = [
        user async for user in users_storage.get_users(
            filter_=filter_, pagination=params.get_pagination(), sort=params.get_sort()
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
        data=UserCreate(
            role=user_create_request.role,
            agent=user_create_request.agent,
        )
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
    updated = None
    async for user in users_storage.update_users(
        filter_=UserFilter(id={target_user.id}),
        data=UserUpdate(
            role=update_data.get("role"),
            agent=update_data.get("agent"),
        ),
    ):
        updated = user
    return UserResponse.from_item(item=updated)


async def delete_user(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin),
    target_user: User = fastapi.Depends(user_dependency),
) -> None:
    await users_storage.delete_user(
        filter_=UserFilter(id={target_user.id})
    )


async def list_user_sessions(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin_or_self),
    target_user: User = fastapi.Depends(user_dependency),
) -> UserSessionsResponse:
    sessions = []
    async for channel in users_storage.get_user_channels(
        filter_=UserChannelFilter(user_id={target_user.id})
    ):
        if channel.actual_session_id is not None:
            sessions.append(channel.actual_session_id)
    return UserSessionsResponse.from_items(items=sessions)


async def create_user_token(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin_or_self),
    target_user: User = fastapi.Depends(user_dependency),
    token_create_request: TokenCreateRequest = fastapi.Body(embed=False),
) -> TokenResponse:
    expires_at = None
    if token_create_request.ttl_days is not None:
        expires_at = utcnow() + datetime.timedelta(days=token_create_request.ttl_days)
    token_info = await users_storage.create_token(
        data=TokenCreate(user_id=target_user.id, expires_at=expires_at)
    )
    return TokenResponse(token=token_info.token, expires_at=token_info.expires_at)


async def delete_user_token(
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
    _: User = fastapi.Depends(is_admin_or_self),
    target_user: User = fastapi.Depends(user_dependency),
    token: str = fastapi.Path(),
) -> None:
    token_info = await users_storage.get_token(
        filter_=TokenFilter(token={token})
    )
    if token_info is None or token_info.user_id != target_user.id:
        raise HTTPNotFound()
    await users_storage.delete_token(
        filter_=TokenFilter(token={token})
    )
