import facet
from typing import Any


class SyncerInterface(facet.AsyncioServiceMixin):
    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        raise NotImplementedError

    async def get(self, key: str) -> Any | None:
        raise NotImplementedError

    async def delete(self, key: str) -> bool:
        raise NotImplementedError
