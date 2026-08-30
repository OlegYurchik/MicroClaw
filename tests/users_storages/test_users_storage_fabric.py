import pytest

from microclaw.users_storages.database.settings import DatabaseUsersStorageSettings
from microclaw.users_storages.database.storage import DatabaseUsersStorage
from microclaw.users_storages.fabric import get_users_storage
from microclaw.users_storages.filesystem.settings import FilesystemUsersStorageSettings
from microclaw.users_storages.filesystem.storage import FilesystemUsersStorage
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage


class TestGetUsersStorage:
    def test_memory(self):
        settings = MemoryUsersStorageSettings()
        result = get_users_storage(settings)
        assert isinstance(result, MemoryUsersStorage)

    def test_filesystem(self):
        settings = FilesystemUsersStorageSettings()
        result = get_users_storage(settings)
        assert isinstance(result, FilesystemUsersStorage)

    def test_database(self):
        settings = DatabaseUsersStorageSettings(dsn="sqlite+aiosqlite:///:memory:")
        result = get_users_storage(settings)
        assert isinstance(result, DatabaseUsersStorage)

    def test_unsupported_raises(self):
        class FakeType:
            value = "unsupported"

        class FakeSettings:
            type = FakeType()

        with pytest.raises(ValueError, match="Unsupported users storage type"):
            get_users_storage(FakeSettings())
