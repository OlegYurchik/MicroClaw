from typing import Any

import facet


class SyncerInterface(facet.AsyncioServiceMixin):
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        raise NotImplementedError

    async def set_if_not_exists(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set key only if it does not exist. Return True if set, False if already present."""
        raise NotImplementedError

    async def get(self, key: str) -> Any | None:
        raise NotImplementedError

    async def delete(self, key: str) -> bool:
        raise NotImplementedError

    async def wait_delete(self, key: str, timeout: float | None = None) -> bool:
        """Block until key is deleted. Return True when deleted, False on timeout."""
        raise NotImplementedError

    async def scan_keys(self, pattern: str) -> list[str]:
        raise NotImplementedError

    async def list_append(self, key: str, value: Any) -> None:
        raise NotImplementedError

    async def list_pop_all(self, key: str) -> list[Any]:
        raise NotImplementedError
