from unittest.mock import AsyncMock, MagicMock

import fastapi
import httpx
import pytest
import pytest_asyncio

from microclaw.api.rest import agents, auth, crons, models, sessions, toolkits, users
from microclaw.api.rest import handlers as rest_handlers
from microclaw.dto import UserRoleEnum
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage
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

    return application


@pytest_asyncio.fixture
async def client(app: fastapi.FastAPI) -> httpx.AsyncClient:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin_user(users_storage: MemoryUsersStorage):
    user = await users_storage.create_user(role=UserRoleEnum.ADMIN)
    token_info = await users_storage.create_token_for_user(user_id=user.id)
    return user, token_info.token


@pytest_asyncio.fixture
async def regular_user(users_storage: MemoryUsersStorage):
    user = await users_storage.create_user(role=UserRoleEnum.USER)
    token_info = await users_storage.create_token_for_user(user_id=user.id)
    return user, token_info.token
