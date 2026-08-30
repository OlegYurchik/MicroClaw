from .exceptions import HTTPForbidden, HTTPUnauthorized
from .schemas import ListQueryParams
import fastapi
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from microclaw.dto import User, UserRoleEnum
from microclaw.resolver import DependencyResolver
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.users_storages import UsersStorageInterface


async def users_storage(
        request: fastapi.Request,
) -> UsersStorageInterface:
    return request.app.state.users_storage


async def sessions_storage(
        request: fastapi.Request,
) -> SessionsStorageInterface:
    return request.app.state.sessions_storage


async def resolver(
        request: fastapi.Request,
) -> DependencyResolver:
    return request.app.state.resolver


async def token(
        credentials: HTTPAuthorizationCredentials | None = fastapi.Depends(
            HTTPBearer(auto_error=False),
        ),
) -> str | None:
    if credentials is not None:
        return credentials.credentials


async def user(
        users_storage: UsersStorageInterface = fastapi.Depends(users_storage),
        token: str | None = fastapi.Depends(token),
) -> User | None:
    if token is not None:
        return await users_storage.get_user_by_token(token=token)


async def auth(
        user: User | None = fastapi.Depends(user),
) -> User:
    if user is None:
        raise HTTPUnauthorized()
    return user


async def is_admin(
        user: User = fastapi.Depends(auth),
) -> User:
    if user.role != UserRoleEnum.ADMIN:
        raise HTTPForbidden()
    return user


async def list_query_params(
        cursor: str | None = fastapi.Query(default=None),
        limit: int = fastapi.Query(default=20, ge=1, le=100),
        sort_by: str | None = fastapi.Query(default=None),
        sort_order: str = fastapi.Query(default="asc", pattern="^(asc|desc)$"),
) -> ListQueryParams:
    return ListQueryParams(
        cursor=cursor,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
