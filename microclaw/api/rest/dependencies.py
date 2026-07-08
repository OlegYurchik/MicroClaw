import fastapi
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from microclaw.dto import User, UserRoleEnum
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.users_storages import UsersStorageInterface
from .exceptions import HTTPForbidden, HTTPUnauthorized


async def users_storage(request: fastapi.Request) -> UsersStorageInterface:
    return request.app.users_storage


async def sessions_storage(request: fastapi.Request) -> SessionsStorageInterface:
    return request.app.sessions_storage


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


async def auth(user: User | None = fastapi.Depends(user)) -> User:
    if user is None:
        raise HTTPUnauthorized()
    return user


async def is_admin(user: User = fastapi.Depends(user)) -> User:
    if user.role is not UserRoleEnum.ADMIN:
        raise HTTPForbidden()
    return user
