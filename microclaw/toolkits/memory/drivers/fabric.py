from .filesystem import FilesystemMemoryDriver
from .interfaces import MemoryDriverInterface
from .settings import MemoryDriverEnum, MemoryDriverSettings


def get_memory_driver(settings: MemoryDriverSettings) -> MemoryDriverInterface:
    match settings.type:
        case MemoryDriverEnum.FILESYSTEM:
            return FilesystemMemoryDriver(settings=settings)
        case _:
            raise ValueError(f"Unsupported memory driver: {settings.type}")
