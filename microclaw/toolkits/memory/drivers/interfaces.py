import datetime
from typing import Protocol


class MemoryDriverInterface(Protocol):
    async def get_soul(self) -> str | None:
        raise NotImplementedError

    async def update_soul(self, content: str) -> None:
        raise NotImplementedError

    async def get_agent(self) -> str | None:
        raise NotImplementedError

    async def update_agent(self, content: str) -> None:
        raise NotImplementedError

    async def get_user(self) -> str | None:
        raise NotImplementedError

    async def update_user(self, content: str) -> None:
        raise NotImplementedError

    async def get_memory(self, date: datetime.date | None = None) -> str | None:
        raise NotImplementedError

    async def update_memory(self, content: str, date: datetime.date | None = None) -> None:
        raise NotImplementedError
