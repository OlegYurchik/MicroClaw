import datetime
import uuid
from typing import Protocol


class MemoryDriverInterface(Protocol):
    async def get_memory(
        self, date: datetime.date | None = None, user_id: uuid.UUID | None = None
    ) -> str | None:
        raise NotImplementedError

    async def append_to_memory(
        self,
        content: str,
        date: datetime.date | None = None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        raise NotImplementedError

    async def memory_search(
        self, query: str, limit: int = 10, user_id: uuid.UUID | None = None
    ) -> list[str]:
        raise NotImplementedError

    async def rewrite_memory(
        self,
        content: str,
        date: datetime.date | None = None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        raise NotImplementedError
