import uuid

import fastapi
from microclaw.api.rest.dependencies import (
    auth,
    is_admin,
    list_query_params,
    sessions_storage as sessions_storage_dep,
    users_storage as users_storage_dep,
)
from microclaw.api.rest.schemas import ListQueryParams
from microclaw.dto import SessionMetadata, Spending, User
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.users_storages import UsersStorageInterface

from .dependencies import is_session_owner
from .schemas import SessionListResponse, SessionResponse


async def create_session(
    sessions_storage: SessionsStorageInterface = fastapi.Depends(
        sessions_storage_dep
    ),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dep),
    current_user: User = fastapi.Depends(auth),
) -> SessionResponse:
    session_id = await sessions_storage.create_session()
    await users_storage.attach_session_to_user(
        user_id=current_user.id,
        session_id=session_id,
        channel_key="rest",
        channel_internal_id=str(current_user.id),
    )
    meta = await sessions_storage.get_session(session_id)
    return SessionResponse.from_item(item=meta)


async def list_sessions(
    params: ListQueryParams = fastapi.Depends(list_query_params),
    sessions_storage: SessionsStorageInterface = fastapi.Depends(
        sessions_storage_dep
    ),
    _: User = fastapi.Depends(is_admin),
) -> SessionListResponse:
    session_ids = [
        session_id
        async for session_id in sessions_storage.get_sessions(
            pagination=params.get_pagination(),
            sort=params.get_sort(),
        )
    ]

    sessions_meta: list[SessionMetadata] = []
    for session_id in session_ids:
        meta = await sessions_storage.get_session(session_id)
        if meta is not None:
            sessions_meta.append(meta)

    response = SessionListResponse.from_items(items=sessions_meta)
    if len(session_ids) == params.limit:
        response.next_cursor = params.next_cursor(len(session_ids))
    return response


async def get_session(
    meta: SessionMetadata = fastapi.Depends(is_session_owner),
) -> SessionResponse:
    return SessionResponse.from_item(item=meta)


async def delete_session(
    session_id: uuid.UUID = fastapi.Path(),
    meta: SessionMetadata = fastapi.Depends(is_session_owner),
    sessions_storage: SessionsStorageInterface = fastapi.Depends(
        sessions_storage_dep
    ),
) -> None:
    await sessions_storage.delete_session(session_id)


async def get_session_spending(
    session_id: uuid.UUID = fastapi.Path(),
    meta: SessionMetadata = fastapi.Depends(is_session_owner),
    sessions_storage: SessionsStorageInterface = fastapi.Depends(
        sessions_storage_dep
    ),
) -> Spending:
    return await sessions_storage.get_spending(session_id)
