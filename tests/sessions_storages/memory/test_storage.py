import uuid

from metaorm import AlreadyExistsError
import pytest

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
async def test_session_crud(memory_sessions_storage):
    await assert_session_crud(memory_sessions_storage)


@pytest.mark.asyncio
async def test_message_crud(memory_sessions_storage):
    await assert_message_crud(memory_sessions_storage)


@pytest.mark.asyncio
async def test_messages_from_last_summarization(memory_sessions_storage):
    await assert_messages_from_last_summarization(memory_sessions_storage)


@pytest.mark.asyncio
async def test_pagination_and_sort(memory_sessions_storage):
    await assert_pagination_and_sort(memory_sessions_storage)


@pytest.mark.asyncio
async def test_delete_sessions_filter(memory_sessions_storage):
    await assert_delete_sessions_filter(memory_sessions_storage)


@pytest.mark.asyncio
async def test_delete_messages_filter(memory_sessions_storage):
    await assert_delete_messages_filter(memory_sessions_storage)


@pytest.mark.asyncio
async def test_create_session_already_exists(memory_sessions_storage):
    session_id = uuid.uuid4()
    await memory_sessions_storage.create_session(
        data=SessionCreate(
            id=session_id,
            channel_key="test",
            channel_internal_id="test",
        )
    )

    with pytest.raises(AlreadyExistsError):
        await memory_sessions_storage.create_session(
            data=SessionCreate(
                id=session_id,
                channel_key="test",
                channel_internal_id="test",
            )
        )
