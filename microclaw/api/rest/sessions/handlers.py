import uuid

from .dependencies import is_session_owner
from .schemas import SessionListResponse, SessionResponse, SpendingResponse
import fastapi

from microclaw.api.rest.dependencies import (
    auth,
    is_admin,
    list_query_params,
)
from microclaw.api.rest.dependencies import (
    sessions_storage as sessions_storage_dep,
)
from microclaw.api.rest.dependencies import (
    users_storage as users_storage_dep,
)
from microclaw.api.rest.schemas import ListQueryParams
from microclaw.dto import Session, User
from microclaw.sessions_storages import SessionsStorageInterface
from microclaw.sessions_storages.dto import SessionCreate
from microclaw.sessions_storages.filters import SessionFilter
from microclaw.users_storages import UsersStorageInterface
from microclaw.users_storages.dto import UserChannelCreate, UserChannelUpdate
from microclaw.users_storages.filters import UserChannelFilter


async def create_session(
    sessions_storage: SessionsStorageInterface = fastapi.Depends(
        sessions_storage_dep
    ),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dep),
    current_user: User = fastapi.Depends(auth),
) -> SessionResponse:
    session = await sessions_storage.create_session(
        data=SessionCreate(
            channel_key="rest",
            channel_internal_id=str(current_user.id),
        )
    )
    channel = None
    async for channel in users_storage.get_user_channels(
        filter_=UserChannelFilter(
            user_id={current_user.id},
            channel_key={"rest"},
            channel_internal_id={str(current_user.id)},
        )
    ):
        break
    if channel is None:
        await users_storage.create_user_channel(
            data=UserChannelCreate(
                user_id=current_user.id,
                channel_key="rest",
                channel_internal_id=str(current_user.id),
                actual_session_id=session.id,
            )
        )
    else:
        async for _ in users_storage.update_user_channels(
            filter_=UserChannelFilter(
                user_id={current_user.id},
                channel_key={"rest"},
                channel_internal_id={str(current_user.id)},
            ),
            data=UserChannelUpdate(actual_session_id=session.id),
        ):
            pass
    return SessionResponse.from_item(item=session)


async def list_sessions(
    params: ListQueryParams = fastapi.Depends(list_query_params),
    sessions_storage: SessionsStorageInterface = fastapi.Depends(
        sessions_storage_dep
    ),
    _: User = fastapi.Depends(is_admin),
) -> SessionListResponse:
    sessions = [
        session
        async for session in sessions_storage.get_sessions(
            pagination=params.get_pagination(),
            sort=params.get_sort(),
        )
    ]

    response = SessionListResponse.from_items(items=sessions)
    if len(sessions) == params.limit:
        response.next_cursor = params.next_cursor(len(sessions))
    return response


async def get_session(
    meta: Session = fastapi.Depends(is_session_owner),
) -> SessionResponse:
    return SessionResponse.from_item(item=meta)


async def delete_session(
    session_id: uuid.UUID = fastapi.Path(),
    meta: Session = fastapi.Depends(is_session_owner),
    sessions_storage: SessionsStorageInterface = fastapi.Depends(
        sessions_storage_dep
    ),
) -> None:
    await sessions_storage.delete_session(
        filter_=SessionFilter(id={session_id})
    )


async def get_session_spending(
    meta: Session = fastapi.Depends(is_session_owner),
) -> SpendingResponse:
    return SpendingResponse.from_spending(meta.spending)
