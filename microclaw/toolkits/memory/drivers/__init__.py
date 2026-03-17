from .fabric import get_memory_driver
from .filesystem import FilesystemMemoryDriverSettings


MemoryDriverSettingsType = FilesystemMemoryDriverSettings


__all__ = (
    "MemoryDriverSettingsType",
    # fabric
    "get_memory_driver",
)
