import pytest
import pytest_asyncio

from microclaw.users_storages.database.settings import DatabaseUsersStorageSettings
from microclaw.users_storages.database.storage import DatabaseUsersStorage
from microclaw.users_storages.filesystem.settings import FilesystemUsersStorageSettings
from microclaw.users_storages.filesystem.storage import FilesystemUsersStorage
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage


@pytest.fixture
def memory_users_storage() -> MemoryUsersStorage:
    return MemoryUsersStorage(settings=MemoryUsersStorageSettings())


@pytest_asyncio.fixture
async def filesystem_users_storage(tmp_path) -> FilesystemUsersStorage:
    settings = FilesystemUsersStorageSettings(path=tmp_path / "users")
    storage = FilesystemUsersStorage(settings=settings)
    yield storage


@pytest_asyncio.fixture
async def database_users_storage(tmp_path) -> DatabaseUsersStorage:
    db_path = tmp_path / "users.db"
    settings = DatabaseUsersStorageSettings(dsn=f"sqlite+aiosqlite:///{db_path}")
    storage = DatabaseUsersStorage(settings=settings)
    await storage.start()
    yield storage
