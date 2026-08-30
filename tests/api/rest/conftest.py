import secrets
from unittest.mock import AsyncMock, MagicMock

import fastapi
import httpx
import pytest
import pytest_asyncio

from microclaw.api.rest import (
    agents,
    auth,
    crons,
    models,
    sessions,
    toolkits,
    users,
)
from microclaw.api.rest import (
    handlers as rest_handlers,
)
from microclaw.dto import UserRoleEnum
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage
from microclaw.users_storages.dto import TokenCreate, UserCreate
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage


@pytest.fixture
def users_storage() -> MemoryUsersStorage:
    return MemoryUsersStorage(settings=MemoryUsersStorageSettings())


@pytest.fixture
def sessions_storage() -> MemorySessionsStorage:
    return MemorySessionsStorage(settings=MemorySessionsStorageSettings())


@pytest.fixture
def resolver() -> MagicMock:
    mock = MagicMock()
    mock.settings.agents = {}
    mock.settings.models = {}
    mock.settings.toolkits = {}
    mock.resolve_agents = AsyncMock(return_value={})
    return mock


@pytest.fixture
def app(users_storage, sessions_storage, resolver) -> fastapi.FastAPI:
    application = fastapi.FastAPI()
    application.state.users_storage = users_storage
    application.state.sessions_storage = sessions_storage
    application.state.resolver = resolver

    application.include_router(auth.get_router(), prefix="/auth")
    application.include_router(agents.get_router(), prefix="/agents")
    application.include_router(crons.get_router(), prefix="/crons")
    application.include_router(models.get_router(), prefix="/models")
    application.include_router(toolkits.get_router(), prefix="/toolkits")
    application.include_router(users.get_router(), prefix="/users")
    application.include_router(sessions.get_router(), prefix="/sessions")
    application.get("/health")(rest_handlers.health)

    # Override cron scheduler dependency to avoid actual scheduling in tests
    from microclaw.api.rest.crons.handlers import CronService, get_cron_service

    mock_cron_service = CronService()
    mock_cron_service.schedule = AsyncMock()
    mock_cron_service.unschedule = AsyncMock()
    application.dependency_overrides[get_cron_service] = lambda: mock_cron_service
    return application


@pytest.fixture
def session_factory(sessions_storage, users_storage):
    async def _make(user, channel_key="rest", channel_internal_id=None):
        from microclaw.sessions_storages.dto import SessionCreate
        from microclaw.users_storages.dto import UserChannelCreate, UserChannelUpdate
        from microclaw.users_storages.filters import UserChannelFilter

        channel_internal_id = channel_internal_id or str(user.id)
        session = await sessions_storage.create_session(
            data=SessionCreate(
                channel_key=channel_key, channel_internal_id=channel_internal_id
            )
        )
        await users_storage.create_user_channel(
            data=UserChannelCreate(
                user_id=user.id,
                channel_key=channel_key,
                channel_internal_id=channel_internal_id,
            )
        )
        async for _ in users_storage.update_user_channels(
            filter_=UserChannelFilter(
                user_id={user.id},
                channel_key={channel_key},
                channel_internal_id={channel_internal_id},
            ),
            data=UserChannelUpdate(actual_session_id=session.id),
        ):
            pass
        return session.id

    return _make


@pytest_asyncio.fixture
async def client(app: fastapi.FastAPI) -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture
async def admin_user(users_storage: MemoryUsersStorage):
    user = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.ADMIN))
    token_obj = await users_storage.create_token(
        data=TokenCreate(
            user_id=user.id, token=secrets.token_urlsafe(32), expires_at=None
        )
    )
    return user, token_obj.token


@pytest_asyncio.fixture
async def regular_user(users_storage: MemoryUsersStorage):
    user = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.USER))
    token_obj = await users_storage.create_token(
        data=TokenCreate(
            user_id=user.id, token=secrets.token_urlsafe(32), expires_at=None
        )
    )
    return user, token_obj.token
