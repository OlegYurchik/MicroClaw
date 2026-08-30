from .fabric import get_users_storage
from .filesystem import FilesystemUsersStorageSettings
from .interfaces import UsersStorageInterface
from .memory import MemoryUsersStorageSettings
from .settings import UsersStorageSettings


UsersStorageSettingsType = MemoryUsersStorageSettings | FilesystemUsersStorageSettings


__all__ = (
    "UsersStorageSettingsType",
    # fabric
    "get_users_storage",
    # interfaces
    "UsersStorageInterface",
    # settings
    "UsersStorageSettings",
)
