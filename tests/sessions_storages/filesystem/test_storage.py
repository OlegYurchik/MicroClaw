import pytest

from tests.sessions_storages.helpers import (
    assert_delete_messages_filter,
    assert_delete_session_cascade,
    assert_delete_sessions_filter,
    assert_message_crud,
    assert_messages_from_last_summarization,
    assert_pagination_and_sort,
    assert_session_crud,
)


@pytest.mark.asyncio
async def test_session_crud(filesystem_sessions_storage):
    await assert_session_crud(filesystem_sessions_storage)


@pytest.mark.asyncio
async def test_message_crud(filesystem_sessions_storage):
    await assert_message_crud(filesystem_sessions_storage)


@pytest.mark.asyncio
async def test_messages_from_last_summarization(filesystem_sessions_storage):
    await assert_messages_from_last_summarization(filesystem_sessions_storage)


@pytest.mark.asyncio
async def test_pagination_and_sort(filesystem_sessions_storage):
    await assert_pagination_and_sort(filesystem_sessions_storage)


@pytest.mark.asyncio
async def test_delete_sessions_filter(filesystem_sessions_storage):
    await assert_delete_sessions_filter(filesystem_sessions_storage)


@pytest.mark.asyncio
async def test_delete_messages_filter(filesystem_sessions_storage):
    await assert_delete_messages_filter(filesystem_sessions_storage)


@pytest.mark.asyncio
async def test_delete_session_cascade(filesystem_sessions_storage):
    await assert_delete_session_cascade(filesystem_sessions_storage)
