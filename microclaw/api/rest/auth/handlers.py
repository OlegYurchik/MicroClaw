import datetime

from .schemas import TokenCreateRequest
import fastapi

from microclaw.api.rest.dependencies import auth, users_storage
from microclaw.api.rest.exceptions import HTTPNotFound
from microclaw.api.rest.schemas import TokenResponse, UserResponse
from microclaw.dto import User
from microclaw.users_storages import UsersStorageInterface
from microclaw.users_storages.dto import TokenCreate
from microclaw.users_storages.filters import TokenFilter, UserFilter


async def me(
        user: User = fastapi.Depends(auth),
) -> UserResponse:
    return UserResponse.from_item(item=user)


async def create_token(
        request: TokenCreateRequest,
        storage: UsersStorageInterface = fastapi.Depends(users_storage),
) -> TokenResponse:
    user = await storage.get_user(
        filter_=UserFilter(id={request.user_id})
    )
    if user is None:
        raise HTTPNotFound(detail="User not found")
    expires_at = None
    if request.ttl_days is not None:
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=request.ttl_days)
    token_info = await storage.create_token(
        data=TokenCreate(user_id=request.user_id, expires_at=expires_at)
    )
    return TokenResponse(token=token_info.token, expires_at=token_info.expires_at)


async def delete_token(
        token: str,
        storage: UsersStorageInterface = fastapi.Depends(users_storage),
) -> None:
    await storage.delete_token(filter_=TokenFilter(token={token}))
