from unittest.mock import AsyncMock, MagicMock

import fastapi
import httpx
import pytest
import pytest_asyncio

from microclaw.api.rest.openai.router import get_router
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage


@pytest.fixture
def openai_resolver():
    mock = MagicMock()
    mock.settings.agents = {"gpt-4": MagicMock()}
    mock.resolve_agents = AsyncMock(return_value=mock.settings.agents)
    return mock


@pytest.fixture
def openai_sessions_storage():
    return MemorySessionsStorage(settings=MemorySessionsStorageSettings())


@pytest.fixture
def openai_app(openai_resolver, openai_sessions_storage):
    app = fastapi.FastAPI()
    app.state.resolver = openai_resolver
    app.state.sessions_storage = openai_sessions_storage
    router = get_router(app)
    app.include_router(router, prefix="/openai")
    return app


@pytest_asyncio.fixture
async def openai_client(openai_app: fastapi.FastAPI):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=openai_app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_list_models_endpoint(openai_client: httpx.AsyncClient):
    response = await openai_client.get("/openai/models")
    assert response.status_code == 200
    data = response.json()
    assert any(m["id"] == "gpt-4" for m in data.get("data", []))


@pytest.mark.asyncio
async def test_chat_completions_endpoint_agent_not_found(
    openai_client: httpx.AsyncClient,
):
    response = await openai_client.post(
        "/openai/chat/completions",
        json={
            "model": "unknown-model",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 404
