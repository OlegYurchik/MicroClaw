from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from microclaw.api.rest.exceptions import HTTPBadRequest, HTTPNotFound
from microclaw.api.rest.openai.handlers import (
    _rest_context,
    _stream,
    _sync,
    list_models,
    run_completion,
)
from microclaw.channels.utils import AgentMessageSaver
from microclaw.dto import AgentMessage
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage
from microclaw.toolkits.context import TOOLKIT_CONTEXT
from microclaw.utils.context import REQUEST_ID_CONTEXT, SESSION_ID_CONTEXT


@pytest.fixture
def handlers_sessions_storage():
    return MemorySessionsStorage(settings=MemorySessionsStorageSettings())


@pytest.fixture
def handlers_resolver():
    mock = MagicMock()
    mock.settings.agents = {"gpt-4": MagicMock()}
    mock.resolve_agents = AsyncMock(return_value=mock.settings.agents)
    return mock


@pytest.fixture
def mock_agent():
    agent = MagicMock()

    async def _ask(*, messages, stream):
        yield AgentMessage(role="assistant", text="Hello")
        if not stream:
            yield AgentMessage(role="assistant", text=" world", spending=None)

    agent.ask = _ask
    agent.has_pending_interrupt = AsyncMock(return_value=False)

    async def _resume(*, session_id, decision, new_messages):
        yield AgentMessage(role="assistant", text="Resumed")

    agent.resume_after_confirmation = _resume
    return agent


@pytest.mark.asyncio
async def test_run_completion_agent_not_found(
    handlers_resolver, handlers_sessions_storage
):
    handlers_resolver.resolve_agents = AsyncMock(return_value={})

    with pytest.raises(HTTPNotFound):
        await run_completion(
            model="unknown",
            messages=[{"role": "user", "content": "hi"}],
            body={},
            resolver=handlers_resolver,
            sessions_storage=handlers_sessions_storage,
        )


@pytest.mark.asyncio
async def test_run_completion_invalid_session_id(
    handlers_resolver, handlers_sessions_storage
):
    with pytest.raises(HTTPBadRequest):
        await run_completion(
            model="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            body={"metadata": {"session_id": "not-a-uuid"}},
            resolver=handlers_resolver,
            sessions_storage=handlers_sessions_storage,
        )


@pytest.mark.asyncio
async def test_run_completion_creates_new_session(
    handlers_resolver, handlers_sessions_storage, mock_agent
):
    agents = {"gpt-4": mock_agent}
    handlers_resolver.resolve_agents = AsyncMock(return_value=agents)

    result = await run_completion(
        model="gpt-4",
        messages=[{"role": "user", "content": "hi"}],
        body={},
        resolver=handlers_resolver,
        sessions_storage=handlers_sessions_storage,
    )

    assert isinstance(result, str)
    assert "Hello" in result


@pytest.mark.asyncio
async def test_run_completion_sync(
    handlers_resolver, handlers_sessions_storage, mock_agent
):
    agents = {"gpt-4": mock_agent}
    handlers_resolver.resolve_agents = AsyncMock(return_value=agents)

    result = await run_completion(
        model="gpt-4",
        messages=[{"role": "user", "content": "hi"}],
        body={"stream": False},
        resolver=handlers_resolver,
        sessions_storage=handlers_sessions_storage,
    )

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_run_completion_stream(
    handlers_resolver, handlers_sessions_storage, mock_agent
):
    agents = {"gpt-4": mock_agent}
    handlers_resolver.resolve_agents = AsyncMock(return_value=agents)

    result = await run_completion(
        model="gpt-4",
        messages=[{"role": "user", "content": "hi"}],
        body={"stream": True},
        resolver=handlers_resolver,
        sessions_storage=handlers_sessions_storage,
    )

    chunks = []
    async for chunk in result:
        chunks.append(chunk)

    assert len(chunks) > 0


@pytest.mark.asyncio
async def test_run_completion_with_decision(
    handlers_resolver, handlers_sessions_storage, mock_agent
):
    mock_agent.has_pending_interrupt = AsyncMock(return_value=True)
    agents = {"gpt-4": mock_agent}
    handlers_resolver.resolve_agents = AsyncMock(return_value=agents)

    result = await run_completion(
        model="gpt-4",
        messages=[{"role": "user", "content": "hi"}],
        body={"metadata": {"decision": "approve"}},
        resolver=handlers_resolver,
        sessions_storage=handlers_sessions_storage,
    )

    assert isinstance(result, str)
    assert "Resumed" in result


@pytest.mark.asyncio
async def test_run_completion_invalid_decision(
    handlers_resolver, handlers_sessions_storage
):
    with pytest.raises(HTTPBadRequest):
        await run_completion(
            model="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            body={"metadata": {"decision": "invalid"}},
            resolver=handlers_resolver,
            sessions_storage=handlers_sessions_storage,
        )


def test_list_models():
    resolver = MagicMock()
    resolver.settings.agents = {"a": MagicMock(), "b": MagicMock()}
    result = list_models(resolver)
    assert result == ["a", "b"]


@pytest.mark.asyncio
async def test_sync_aggregates_text(handlers_sessions_storage):
    from microclaw.sessions_storages.dto import SessionCreate

    session = await handlers_sessions_storage.create_session(
        data=SessionCreate(channel_key="rest", channel_internal_id="")
    )
    session_id = session.id
    request_id = uuid.uuid4()
    saver = AgentMessageSaver(
        sessions_storage=handlers_sessions_storage, session_id=session_id
    )

    async def gen():
        yield AgentMessage(role="assistant", text="Hello")
        yield AgentMessage(role="assistant", text=" world")

    result = await _sync(gen(), saver, session_id, request_id)
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_stream_yields_text(handlers_sessions_storage):
    from microclaw.sessions_storages.dto import SessionCreate

    session = await handlers_sessions_storage.create_session(
        data=SessionCreate(channel_key="rest", channel_internal_id="")
    )
    session_id = session.id
    request_id = uuid.uuid4()
    saver = AgentMessageSaver(
        sessions_storage=handlers_sessions_storage, session_id=session_id
    )

    async def gen():
        yield AgentMessage(role="assistant", text="chunk1")
        yield AgentMessage(role="assistant", text="chunk2")

    chunks = []
    async for chunk in _stream(gen(), saver, session_id, request_id):
        chunks.append(chunk)

    assert chunks == ["chunk1", "chunk2"]


@pytest.mark.asyncio
async def test_rest_context_sets_vars():
    session_id = uuid.uuid4()
    request_id = uuid.uuid4()

    assert SESSION_ID_CONTEXT.get(None) is None
    assert REQUEST_ID_CONTEXT.get(None) is None
    assert TOOLKIT_CONTEXT.get(None) is None

    async with _rest_context(session_id, request_id):
        assert SESSION_ID_CONTEXT.get() == session_id
        assert REQUEST_ID_CONTEXT.get() == request_id
        assert TOOLKIT_CONTEXT.get() is not None

    assert SESSION_ID_CONTEXT.get(None) is None
    assert REQUEST_ID_CONTEXT.get(None) is None
    assert TOOLKIT_CONTEXT.get(None) is None
