from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.api.rest.service import RESTAPIService, UvicornServer
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage


@pytest.fixture
def rest_settings():
    from microclaw.api.rest.settings import RESTAPISettings

    return RESTAPISettings(
        users_storage=MemoryUsersStorageSettings(),
        sessions_storage=MemorySessionsStorageSettings(),
    )


@pytest.fixture
def rest_resolver():
    resolver = MagicMock()
    resolver.resolve_users_storages = AsyncMock(return_value={})
    resolver.resolve_sessions_storages = AsyncMock(return_value={})
    return resolver


@pytest.mark.asyncio
async def test_build_app_includes_routers(rest_settings, rest_resolver):
    service = RESTAPIService(
        settings=rest_settings,
        dependency_resolver=rest_resolver,
    )
    app = await service._build_app()

    paths = list(app.openapi()["paths"].keys())
    assert any("/openai" in p for p in paths)
    assert "/health" in paths
    assert any("/auth" in p for p in paths)
    assert any("/agents" in p for p in paths)
    assert any("/crons" in p for p in paths)
    assert any("/models" in p for p in paths)
    assert any("/toolkits" in p for p in paths)
    assert any("/users" in p for p in paths)
    assert any("/sessions" in p for p in paths)


@pytest.mark.asyncio
async def test_build_app_sets_state(rest_settings, rest_resolver):
    service = RESTAPIService(
        settings=rest_settings,
        dependency_resolver=rest_resolver,
    )
    app = await service._build_app()

    assert isinstance(app.state.users_storage, MemoryUsersStorage)
    assert isinstance(app.state.sessions_storage, MemorySessionsStorage)
    assert app.state.resolver is rest_resolver


@pytest.mark.asyncio
async def test_build_app_cors_middleware(rest_settings, rest_resolver):
    service = RESTAPIService(
        settings=rest_settings,
        dependency_resolver=rest_resolver,
    )
    app = await service._build_app()

    middleware_classes = [m.cls for m in app.user_middleware]
    assert any("CORSMiddleware" in str(cls) for cls in middleware_classes)


@pytest.mark.asyncio
async def test_build_app_users_storage_from_resolver(rest_settings, rest_resolver):
    users_storage = MemoryUsersStorage(settings=MemoryUsersStorageSettings())
    rest_resolver.resolve_users_storages = AsyncMock(
        return_value={"default": users_storage}
    )

    settings = rest_settings.model_copy(update={"users_storage": "default"})
    service = RESTAPIService(
        settings=settings,
        dependency_resolver=rest_resolver,
    )
    app = await service._build_app()

    assert app.state.users_storage is users_storage


@pytest.mark.asyncio
async def test_build_app_sessions_storage_from_resolver(rest_settings, rest_resolver):
    sessions_storage = MemorySessionsStorage(settings=MemorySessionsStorageSettings())
    rest_resolver.resolve_sessions_storages = AsyncMock(
        return_value={"default": sessions_storage}
    )

    settings = rest_settings.model_copy(update={"sessions_storage": "default"})
    service = RESTAPIService(
        settings=settings,
        dependency_resolver=rest_resolver,
    )
    app = await service._build_app()

    assert app.state.sessions_storage is sessions_storage


def test_uvicorn_server_signal_handlers_noop():
    server = UvicornServer(config=MagicMock())
    # Should not raise
    server.install_signal_handlers()
