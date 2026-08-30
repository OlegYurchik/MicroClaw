import asyncio
import fnmatch
import time
from typing import Any

from .dto import StorageItem
from .settings import MemorySyncerSettings

from microclaw.syncers.interfaces import SyncerInterface


class MemorySyncer(SyncerInterface):
    def __init__(self, settings: MemorySyncerSettings):
        self._settings = settings
        self._storage: dict[str, StorageItem] = {}
        self._lists: dict[str, list[Any]] = {}
        self._events: dict[str, asyncio.Event] = {}

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
            event = self._events.pop(key, None)
            if event is not None:
                event.set()
            return True
        return False

    async def wait_delete(self, key: str, timeout: float | None = None) -> bool:
        item = self._storage.get(key)
        if item is None:
            return True
        if item.expire_at is not None and time.time() > item.expire_at:
            del self._storage[key]
            return True

        event = self._events.setdefault(key, asyncio.Event())
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            current = self._storage.get(key)
            if current is None or (
                current.expire_at is not None and time.time() > current.expire_at
            ):
                return True
            return False

    async def scan_keys(self, pattern: str) -> list[str]:
        now = time.time()
        matched: list[str] = []
        for key in list(self._storage.keys()):
            item = self._storage[key]
            if item.expire_at is not None and now > item.expire_at:
                del self._storage[key]
                continue
            if fnmatch.fnmatch(key, pattern):
                matched.append(key)
        return matched

    async def set_if_not_exists(self, key: str, value: Any, ttl: int | None = None) -> bool:
        item = self._storage.get(key)
        if item is not None:
            if item.expire_at is not None and time.time() > item.expire_at:
                del self._storage[key]
            else:
                return False
        await self.set(key, value, ttl)
        return True

    async def list_append(self, key: str, value: Any) -> None:
        if key not in self._lists:
            self._lists[key] = []
        self._lists[key].append(value)

    async def list_pop_all(self, key: str) -> list[Any]:
        values = self._lists.pop(key, [])
        return values
