import datetime

import fastapi

from microclaw.api.rest.schemas import TokenResponse, UserResponse
from microclaw.api.rest.dependencies import auth, users_storage
from microclaw.api.rest.exceptions import HTTPNotFound
from microclaw.dto import User
from microclaw.users_storages import UsersStorageInterface

from .schemas import TokenCreateRequest


async def me(
        user: User = fastapi.Depends(auth),
) -> UserResponse:
    return UserResponse.from_item(item=user)


async def create_token(
        request: TokenCreateRequest,
        storage: UsersStorageInterface = fastapi.Depends(users_storage),
) -> TokenResponse:
    user = await storage.get_user(request.user_id)
    if user is None:
        raise HTTPNotFound(detail="User not found")
    ttl = datetime.timedelta(days=request.ttl_days)
    token_info = await storage.create_token_for_user(user_id=request.user_id, ttl=ttl)
    return TokenResponse(token=token_info.token, expires_at=token_info.expires_at)


async def delete_token(
        token: str,
        storage: UsersStorageInterface = fastapi.Depends(users_storage),
) -> None:
    await storage.delete_token(token)
