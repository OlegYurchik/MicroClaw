from .fabric import get_users_storage
from .interfaces import UsersStorageInterface
from .memory import MemoryUsersStorageSettings
from .settings import UsersStorageSettings
from .filesystem import FilesystemUsersStorageSettings


UsersStorageSettingsType = (
    MemoryUsersStorageSettings |
    FilesystemUsersStorageSettings
)


__all__ = (
    "UsersStorageSettingsType",
    # fabric
    "get_users_storage",
    # interfaces
    "UsersStorageInterface",
    # settings
    "UsersStorageSettings",
)
