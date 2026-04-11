import datetime
import tiktoken

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.settings import ToolKitSettings
from .drivers.fabric import get_memory_driver
from .settings import MemoryToolKitSettings


class MemorySizeExceeded(Exception):
    def __init__(
            self,
            max_tokens: int,
            date: datetime.date | None = None,
    ):
        memory_type = "general" if date is None else f"daily ({date})"
        super().__init__(
            f"Memory size limit ({max_tokens} tokens) exceeded for {memory_type} memory.",
        )


class MemoryToolKit(BaseToolKit[MemoryToolKitSettings]):
    """Tools for managing daily memories and general memory."""

    def __init__(self, key: str, settings: MemoryToolKitSettings):
        super().__init__(key=key, settings=settings)
        self._driver = get_memory_driver(settings=self._settings.driver)

    def _get_tokens_count(self, text: str) -> int:
        if len(text) == 0:
            return 0

        tokenizer = tiktoken.get_encoding("cl100k_base")
        return len(tokenizer.encode(text))

    @tool
    async def get_memory(self, date: datetime.date | None = None) -> str | None:
        """
        Get memory content for a specific date or general memory.

        Args:
            date: Date to get memory for. If None, returns general memory.

        Returns:
            Memory content as string or None if not found
        """
        return await self._driver.get_memory(date)

    @tool
    async def append_to_memory(self, content: str, date: datetime.date | None = None) -> None:
        """
        Append content to memory for a specific date or general memory.

        Args:
            content: Content to append to memory
            date: Date to append memory for. If None, appends to general memory.

        Raises:
            MemorySizeExceeded: If memory size limit is exceeded
        """
        current_content = await self._driver.get_memory(date) or ""
        current_tokens = self._get_tokens_count(current_content)
        new_tokens = self._get_tokens_count(content)
        max_tokens = self._settings.max_memory_tokens
        if current_tokens + new_tokens > max_tokens:
            raise MemorySizeExceeded(
                max_tokens=max_tokens,
                date=date,
            )

        await self._driver.append_to_memory(content, date)

    @tool
    async def memory_search(self, query: str, limit: int = 10) -> list[str]:
        """
        Search memory files for a query.

        Args:
            query: Search query string
            limit: Maximum number of results to return (default: 10)

        Returns:
            List of memory file contents matching the query
        """
        return await self._driver.memory_search(query, limit)

    async def rewrite_memory(self, content: str, date: datetime.date | None = None) -> None:
        await self._driver.rewrite_memory(content, date)
