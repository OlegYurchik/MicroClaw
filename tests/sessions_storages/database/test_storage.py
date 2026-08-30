import pytest

from microclaw.sessions_storages.database.settings import (
    DatabaseSessionsStorageSettings,
)
from microclaw.sessions_storages.database.storage import DatabaseSessionsStorage
from microclaw.sessions_storages.dto import SessionCreate
from tests.sessions_storages.helpers import (
    assert_delete_messages_filter,
    assert_delete_sessions_filter,
    assert_message_crud,
    assert_messages_from_last_summarization,
    assert_pagination_and_sort,
    assert_session_crud,
)


@pytest.mark.asyncio
async def test_session_crud(database_sessions_storage):
    await assert_session_crud(database_sessions_storage)


@pytest.mark.asyncio
async def test_message_crud(database_sessions_storage):
    await assert_message_crud(database_sessions_storage)


@pytest.mark.asyncio
async def test_messages_from_last_summarization(database_sessions_storage):
    await assert_messages_from_last_summarization(database_sessions_storage)


@pytest.mark.asyncio
async def test_pagination_and_sort(database_sessions_storage):
    await assert_pagination_and_sort(database_sessions_storage)


@pytest.mark.asyncio
async def test_delete_sessions_filter(database_sessions_storage):
    await assert_delete_sessions_filter(database_sessions_storage)


@pytest.mark.asyncio
async def test_delete_messages_filter(database_sessions_storage):
    await assert_delete_messages_filter(database_sessions_storage)


@pytest.mark.asyncio
async def test_start_creates_tables(tmp_path):
    db_path = tmp_path / "sessions.db"
    settings = DatabaseSessionsStorageSettings(dsn=f"sqlite+aiosqlite:///{db_path}")
    storage = DatabaseSessionsStorage(settings=settings)
    await storage.start()
    session = await storage.create_session(
        data=SessionCreate(channel_key="x", channel_internal_id="y")
    )
    assert session is not None
