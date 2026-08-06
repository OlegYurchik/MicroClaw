import datetime
import uuid

import tiktoken

from langgraph.types import interrupt

from microclaw.dto import DecisionEnum
from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.capabilities import DiscoveryCapability, ToolKitCapability
from microclaw.toolkits.context import get_toolkit_context
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction
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

    required_capabilities: list[ToolKitCapability] = [
        ToolKitCapability.CURRENT_USER,
    ]
    write_capabilities: list[ToolKitCapability] = [
        ToolKitCapability.CURRENT_USER,
    ]
    discovery_capabilities: list[DiscoveryCapability] = []

    def __init__(self, key: str, settings: MemoryToolKitSettings):
        super().__init__(key=key, settings=settings)
        self._driver = get_memory_driver(settings=self._settings.driver)

    @tool
    async def get_memory(
        self,
        date: datetime.date | None = None,
        user_id: str | None = None,
    ) -> str | None:
        """
        Get memory content for a specific date or general memory.

        Args:
            date: Date to get memory for. If None, returns general memory.
            user_id: UUID of the user whose memory to read. If None, reads
                the current user's memory (requires CURRENT_USER).

        Returns:
            Memory content as string or None if not found
        """
        try:
            target_id = await self._resolve_target_id(user_id)
        except RuntimeError:
            return None
        return await self._driver.get_memory(date, user_id=target_id)

    @tool
    async def append_to_memory(
        self,
        content: str,
        date: datetime.date | None = None,
        user_id: str | None = None,
    ) -> None:
        """
        Append content to memory for a specific date or general memory.

        Args:
            content: Content to append to memory
            date: Date to append memory for. If None, appends to general memory.
            user_id: UUID of the user whose memory to modify. If None, modifies
                the current user's memory (requires CURRENT_USER write).

        Returns:
            None - indicates successful operation

        Raises:
            MemorySizeExceeded: If memory size limit is exceeded
        """
        if self._settings.edit_mode is PermissionModeEnum.DENY:
            raise PermissionError("Memory editing is not allowed")

        target_id = await self._resolve_target_id(user_id)
        if user_id is not None:
            ctx = get_toolkit_context()
            if (
                ctx.all_users_accessor is not None
                and not ctx.all_users_accessor.writable
            ):
                raise PermissionError("Cross-user memory write access not granted")

        if self._settings.edit_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": "Append to memory?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        current_content = await self._driver.get_memory(date, user_id=target_id) or ""
        current_tokens = self._get_tokens_count(current_content)
        new_tokens = self._get_tokens_count(content)
        max_tokens = self._settings.max_memory_tokens
        if current_tokens + new_tokens > max_tokens:
            raise MemorySizeExceeded(max_tokens=max_tokens, date=date)

        await self._driver.append_to_memory(content, date, user_id=target_id)

    @tool
    async def memory_search(
        self,
        query: str,
        limit: int = 10,
        user_id: str | None = None,
    ) -> list[str]:
        """
        Search memory files for a query.

        Args:
            query: Search query string
            limit: Maximum number of results to return (default: 10)
            user_id: UUID of the user whose memory to search. If None, searches
                the current user's memory (requires CURRENT_USER).

        Returns:
            List of memory file contents matching the query
        """
        try:
            target_id = await self._resolve_target_id(user_id)
        except RuntimeError:
            return []
        return await self._driver.memory_search(query, limit, user_id=target_id)

    @tool
    async def rewrite_memory(
        self,
        content: str,
        date: datetime.date | None = None,
        user_id: str | None = None,
    ) -> None:
        """
        Rewrite memory content for a specific date or general memory.

        Args:
            content: New content to write to memory
            date: Date to rewrite memory for. If None, rewrites general memory.
            user_id: UUID of the user whose memory to modify. If None, modifies
                the current user's memory (requires CURRENT_USER write).

        Returns:
            None - indicates successful operation
        """
        if self._settings.edit_mode is PermissionModeEnum.DENY:
            raise PermissionError("Memory editing is not allowed")

        target_id = await self._resolve_target_id(user_id)
        if user_id is not None:
            ctx = get_toolkit_context()
            if (
                ctx.all_users_accessor is not None
                and not ctx.all_users_accessor.writable
            ):
                raise PermissionError("Cross-user memory write access not granted")

        if self._settings.edit_mode is PermissionModeEnum.REQUEST:
            decision = interrupt({"description": "Rewrite memory?"})
            if decision == DecisionEnum.REJECT.value:
                raise UserDeniedAction()

        await self._driver.rewrite_memory(content, date, user_id=target_id)

    def _get_tokens_count(self, text: str) -> int:
        if len(text) == 0:
            return 0
        tokenizer = tiktoken.get_encoding("cl100k_base")
        return len(tokenizer.encode(text))

    async def _resolve_target_id(self, user_id: str | None) -> uuid.UUID:
        """
        Resolve target user ID for memory operations.

        If user_id is provided and differs from current user, verifies
        cross-user access through all_users_accessor.
        """
        ctx = get_toolkit_context()
        if ctx is None or ctx.current_user_accessor is None:
            raise RuntimeError("No active channel context")
        me = await ctx.current_user_accessor.get()
        if me is None:
            raise RuntimeError("No current user")
        if user_id is None:
            return me.id
        target_id = uuid.UUID(user_id)
        if target_id != me.id and ctx.all_users_accessor is None:
            raise PermissionError("Cross-user memory access not granted")
        return target_id
