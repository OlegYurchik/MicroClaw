import datetime

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.settings import ToolKitSettings
from .drivers.fabric import get_memory_driver
from .settings import MemoryToolKitSettings


class MemoryToolKit(BaseToolKit[MemoryToolKitSettings]):
    """Tools for managing memory including soul, agent, user profiles and daily memories."""

    def __init__(self, key: str, settings: MemoryToolKitSettings):
        super().__init__(key=key, settings=settings)
        self._driver = get_memory_driver(settings=self._settings.driver)

    @tool
    async def get_soul(self) -> str | None:
        """
        Get the soul content.

        Returns:
            Soul content as string or None if not found
        """
        return await self._driver.get_soul()

    @tool
    async def update_soul(self, content: str) -> None:
        """
        Update the soul content.

        Args:
            content: New soul content to save
        """
        await self._driver.update_soul(content)

    @tool
    async def get_agent(self) -> str | None:
        """
        Get the agent profile content.

        Returns:
            Agent profile content as string or None if not found
        """
        return await self._driver.get_agent()

    @tool
    async def update_agent(self, content: str) -> None:
        """
        Update the agent profile content.

        Args:
            content: New agent profile content to save
        """
        await self._driver.update_agent(content)

    @tool
    async def get_user(self) -> str | None:
        """
        Get the user profile content.

        Returns:
            User profile content as string or None if not found
        """
        return await self._driver.get_user()

    @tool
    async def update_user(self, content: str) -> None:
        """
        Update the user profile content.

        Args:
            content: New user profile content to save
        """
        await self._driver.update_user(content)

    @tool
    async def get_memory(self, date: datetime.date | None = None) -> str | None:
        """
        Get memory content for a specific date.

        Args:
            date: Date to get memory for. If None, uses today's date.

        Returns:
            Memory content as string or None if not found
        """
        return await self._driver.get_memory(date)

    @tool
    async def update_memory(self, content: str, date: datetime.date | None = None) -> None:
        """
        Update memory content for a specific date.

        Args:
            content: New memory content to save
            date: Date to save memory for. If None, uses today's date.
        """
        await self._driver.update_memory(content, date)
