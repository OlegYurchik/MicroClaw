from dataclasses import dataclass
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
    webhooks,
)
from microclaw.api.rest import handlers as rest_handlers
from microclaw.cron.service import CronService
from microclaw.dto import User, UserRoleEnum
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage
from microclaw.users_storages.dto import UserCreate
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage
from microclaw.users_storages.utils import create_token_for_user


@dataclass
class UserWithToken:
    user: User
    token: str

    def __iter__(self):
        return iter((self.user, self.token))


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
    mock.resolve_global_webhooks = AsyncMock(return_value={})
    return mock


@pytest.fixture
def app(users_storage, sessions_storage, resolver) -> fastapi.FastAPI:
    application = fastapi.FastAPI()
    application.state.users_storage = users_storage
    application.state.sessions_storage = sessions_storage
    application.state.resolver = resolver

    from microclaw.api.rest.dependencies import cron_service as cron_service_dep

    mock_cron_service = CronService()
    mock_cron_service.schedule = AsyncMock()
    mock_cron_service.unschedule = AsyncMock()
    application.state.cron_service = mock_cron_service
    application.dependency_overrides[cron_service_dep] = lambda: mock_cron_service

    application.include_router(auth.get_router(), prefix="/auth")
    application.include_router(agents.get_router(), prefix="/agents")
    application.include_router(crons.get_router(), prefix="/crons")
    application.include_router(webhooks.get_router(), prefix="/webhooks")
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
    user = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.ADMIN))
    token_info = await create_token_for_user(users_storage, user_id=user.id)
    return UserWithToken(user=user, token=token_info.token)


@pytest_asyncio.fixture
async def regular_user(users_storage: MemoryUsersStorage):
    user = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.USER))
    token_info = await create_token_for_user(users_storage, user_id=user.id)
    return UserWithToken(user=user, token=token_info.token)
