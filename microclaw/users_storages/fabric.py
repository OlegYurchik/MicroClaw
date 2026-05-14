from .interfaces import UsersStorageInterface
from .memory import MemoryUsersStorage
from .filesystem import FilesystemUsersStorage
from .database import DatabaseUsersStorage
from .settings import UsersStorageSettings, UsersStorageTypeEnum


def get_users_storage(settings: UsersStorageSettings) -> UsersStorageInterface:
    match settings.type:
        case UsersStorageTypeEnum.MEMORY:
            return MemoryUsersStorage(settings=settings)
        case UsersStorageTypeEnum.FILESYSTEM:
            return FilesystemUsersStorage(settings=settings)
        case UsersStorageTypeEnum.DATABASE:
            return DatabaseUsersStorage(settings=settings)
        case _:
            raise ValueError(f"Unsupported users storage type: {settings.type.value}")
