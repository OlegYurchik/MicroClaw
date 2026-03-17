import datetime
import pathlib
from typing import Literal

from pydantic import Field

from .interfaces import MemoryDriverInterface
from .settings import MemoryDriverEnum, MemoryDriverSettings


class FilesystemMemoryDriverSettings(MemoryDriverSettings):
    type: Literal[MemoryDriverEnum.FILESYSTEM] = MemoryDriverEnum.FILESYSTEM
    workspace: pathlib.Path = Field(
        default=pathlib.Path.cwd() / ".workspace",
        description="Directory path where memory files will be stored",
    )


class FilesystemMemoryDriver(MemoryDriverInterface):
    def __init__(self, settings: FilesystemMemoryDriverSettings):
        self._workspace = pathlib.Path(settings.workspace)
        self._workspace.mkdir(parents=True, exist_ok=True)
        self._memory_dir = self._workspace / "memory"
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    async def get_soul(self) -> str | None:
        return await self._read_file(self._workspace / "SOUL.md")

    async def update_soul(self, content: str) -> None:
        await self._write_file(self._workspace / "SOUL.md", content)

    async def get_agent(self) -> str | None:
        return await self._read_file(self._workspace / "AGENT.md")

    async def update_agent(self, content: str) -> None:
        await self._write_file(self._workspace / "AGENT.md", content)

    async def get_user(self) -> str | None:
        return await self._read_file(self._workspace / "USER.md")

    async def update_user(self, content: str) -> None:
        await self._write_file(self._workspace / "USER.md", content)

    async def get_memory(self, date: datetime.date | None = None) -> str | None:
        if date is None:
            date = datetime.date.today()
        filename = date.strftime("%Y-%m-%d.md")
        return await self._read_file(self._memory_dir / filename)

    async def update_memory(self, content: str, date: datetime.date | None = None) -> None:
        if date is None:
            date = datetime.date.today()
        filename = date.strftime("%Y-%m-%d.md")
        await self._write_file(self._memory_dir / filename, content)

    async def _read_file(self, path: pathlib.Path) -> str | None:
        path.touch(exist_ok=True)
        return path.read_text(encoding="utf-8")

    async def _write_file(self, path: pathlib.Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
