import pytest

from tests.users_storages.helpers import (
    assert_cron_crud,
    assert_delete_users_filter,
    assert_pagination_and_sort,
    assert_token_crud,
    assert_user_channel_crud,
    assert_user_crud,
)


@pytest.mark.asyncio
async def test_user_crud(filesystem_users_storage):
    await assert_user_crud(filesystem_users_storage)


@pytest.mark.asyncio
async def test_user_channel_crud(filesystem_users_storage):
    await assert_user_channel_crud(filesystem_users_storage)


@pytest.mark.asyncio
async def test_token_crud(filesystem_users_storage):
    await assert_token_crud(filesystem_users_storage)


@pytest.mark.asyncio
async def test_cron_crud(filesystem_users_storage):
    await assert_cron_crud(filesystem_users_storage)


@pytest.mark.asyncio
async def test_pagination_and_sort(filesystem_users_storage):
    await assert_pagination_and_sort(filesystem_users_storage)


@pytest.mark.asyncio
async def test_delete_users_filter(filesystem_users_storage):
    await assert_delete_users_filter(filesystem_users_storage)
