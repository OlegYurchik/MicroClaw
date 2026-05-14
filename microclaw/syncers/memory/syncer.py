import time
from typing import Any

from microclaw.syncers.interfaces import SyncerInterface
from .dto import StorageItem
from .settings import MemorySyncerSettings


class MemorySyncer(SyncerInterface):
    def __init__(self, settings: MemorySyncerSettings):
        self._settings = settings
        self._storage: dict[str, StorageItem] = {}

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expire_at = time.time() + ttl if ttl is not None else None
        self._storage[key] = StorageItem(value=value, expire_at=expire_at)

    async def get(self, key: str) -> Any | None:
        if key not in self._storage:
            return None

        item = self._storage[key]

        if item.expire_at is not None and time.time() > item.expire_at:
            del self._storage[key]
            return None

        return item.value

    async def delete(self, key: str) -> bool:
        if key in self._storage:
            del self._storage[key]
            return True
        return False
