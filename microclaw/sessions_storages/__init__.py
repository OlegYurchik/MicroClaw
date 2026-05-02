from .fabric import get_sessions_storage
from .filesystem import FilesystemSessionsStorageSettings
from .interfaces import SessionsStorageInterface
from .memory import MemorySessionsStorageSettings
from .settings import SessionsStorageSettings
from .database import DatabaseSessionsStorageSettings


SessionsStorageSettingsType = (
    MemorySessionsStorageSettings |
    FilesystemSessionsStorageSettings |
    DatabaseSessionsStorageSettings
)


__all__ = (
    "SessionsStorageSettingsType",
    # fabric
    "get_sessions_storage",
    # interfaces
    "SessionsStorageInterface",
    # settings
    "SessionsStorageSettings",
)
