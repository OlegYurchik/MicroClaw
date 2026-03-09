from .interfaces import SessionsStorageInterface
from .memory import MemorySessionsStorage
from .filesystem import FilesystemSessionsStorage
from .settings import SessionsStorageSettings, SessionsStorageTypeEnum


def get_sessions_storage(settings: SessionsStorageSettings) -> SessionsStorageInterface:
    match settings.type:
        case SessionsStorageTypeEnum.MEMORY:
            return MemorySessionsStorage(settings=settings)
        case SessionsStorageTypeEnum.FILESYSTEM:
            return FilesystemSessionsStorage(settings=settings)
        case _:
            raise ValueError(f"Unsupported sessions storage type: {settings.type.value}")
