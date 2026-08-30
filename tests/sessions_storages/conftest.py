import pytest
import pytest_asyncio

from microclaw.sessions_storages.database.settings import (
    DatabaseSessionsStorageSettings,
)
from microclaw.sessions_storages.database.storage import DatabaseSessionsStorage
from microclaw.sessions_storages.filesystem.settings import (
    FilesystemSessionsStorageSettings,
)
from microclaw.sessions_storages.filesystem.storage import FilesystemSessionsStorage
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage


@pytest.fixture
def memory_sessions_storage() -> MemorySessionsStorage:
    return MemorySessionsStorage(settings=MemorySessionsStorageSettings())


@pytest_asyncio.fixture
async def filesystem_sessions_storage(tmp_path) -> FilesystemSessionsStorage:
    settings = FilesystemSessionsStorageSettings(path=tmp_path / "sessions")
    storage = FilesystemSessionsStorage(settings=settings)
    yield storage


@pytest_asyncio.fixture
async def database_sessions_storage(tmp_path) -> DatabaseSessionsStorage:
    db_path = tmp_path / "sessions.db"
    settings = DatabaseSessionsStorageSettings(dsn=f"sqlite+aiosqlite:///{db_path}")
    storage = DatabaseSessionsStorage(settings=settings)
    await storage.start()
    yield storage
