import pytest

from microclaw.sessions_storages.database.settings import (
    DatabaseSessionsStorageSettings,
)
from microclaw.sessions_storages.database.storage import DatabaseSessionsStorage
from microclaw.sessions_storages.fabric import get_sessions_storage
from microclaw.sessions_storages.filesystem.settings import (
    FilesystemSessionsStorageSettings,
)
from microclaw.sessions_storages.filesystem.storage import FilesystemSessionsStorage
from microclaw.sessions_storages.memory.settings import MemorySessionsStorageSettings
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage


class TestGetSessionsStorage:
    def test_memory(self):
        settings = MemorySessionsStorageSettings()
        result = get_sessions_storage(settings)
        assert isinstance(result, MemorySessionsStorage)

    def test_filesystem(self):
        settings = FilesystemSessionsStorageSettings()
        result = get_sessions_storage(settings)
        assert isinstance(result, FilesystemSessionsStorage)

    def test_database(self):
        settings = DatabaseSessionsStorageSettings(dsn="sqlite+aiosqlite:///:memory:")
        result = get_sessions_storage(settings)
        assert isinstance(result, DatabaseSessionsStorage)

    def test_unsupported_raises(self):
        class FakeType:
            value = "unsupported"

        class FakeSettings:
            type = FakeType()

        with pytest.raises(ValueError, match="Unsupported sessions storage type"):
            get_sessions_storage(FakeSettings())
