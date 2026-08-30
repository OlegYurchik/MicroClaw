from metaorm import NotFoundError
import pytest

from microclaw.users_storages.database.settings import DatabaseUsersStorageSettings
from microclaw.users_storages.database.storage import DatabaseUsersStorage
from microclaw.users_storages.dto import TokenCreate, TokenUpdate, UserCreate
from tests.users_storages.helpers import (
    assert_cron_crud,
    assert_delete_users_filter,
    assert_pagination_and_sort,
    assert_token_crud,
    assert_user_channel_crud,
    assert_user_crud,
)


@pytest.mark.asyncio
async def test_user_crud(database_users_storage):
    await assert_user_crud(database_users_storage)


@pytest.mark.asyncio
async def test_user_channel_crud(database_users_storage):
    await assert_user_channel_crud(database_users_storage)


@pytest.mark.asyncio
async def test_token_crud(database_users_storage):
    await assert_token_crud(database_users_storage)


@pytest.mark.asyncio
async def test_cron_crud(database_users_storage):
    await assert_cron_crud(database_users_storage)


@pytest.mark.asyncio
async def test_pagination_and_sort(database_users_storage):
    await assert_pagination_and_sort(database_users_storage)


@pytest.mark.asyncio
async def test_delete_users_filter(database_users_storage):
    await assert_delete_users_filter(database_users_storage)


@pytest.mark.asyncio
async def test_start_creates_tables(tmp_path):
    db_path = tmp_path / "users.db"
    settings = DatabaseUsersStorageSettings(dsn=f"sqlite+aiosqlite:///{db_path}")
    storage = DatabaseUsersStorage(settings=settings)
    await storage.start()
    user = await storage.create_user(data=UserCreate())
    assert user is not None


@pytest.mark.asyncio
async def test_update_token_not_found_raises(database_users_storage):
    with pytest.raises(NotFoundError):
        await database_users_storage.update_token(
            "nonexistent", data=TokenUpdate(expires_at=None)
        )


@pytest.mark.asyncio
async def test_create_token_with_duplicate_raises(database_users_storage):
    user = await database_users_storage.create_user(data=UserCreate())
    await database_users_storage.create_token(
        data=TokenCreate(user_id=user.id, token="dup")
    )
    with pytest.raises(Exception):
        await database_users_storage.create_token(
            data=TokenCreate(user_id=user.id, token="dup")
        )
