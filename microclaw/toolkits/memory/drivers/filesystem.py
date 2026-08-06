import datetime
import difflib
import pathlib
import uuid

import aiofiles
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
    _MEMORY_SUBDIR = "memory"
    _GENERAL_FILENAME = "MEMORY.md"

    def __init__(self, settings: FilesystemMemoryDriverSettings):
        self._workspace = pathlib.Path(settings.workspace)
        self._workspace.mkdir(parents=True, exist_ok=True)

    async def get_memory(
        self, date: datetime.date | None = None, user_id: uuid.UUID | None = None
    ) -> str | None:
        workspace = self._get_user_workspace(user_id)
        if date is None:
            return await self._read_file(workspace / self._GENERAL_FILENAME)
        return await self._read_file(
            workspace / self._MEMORY_SUBDIR / date.strftime("%Y-%m-%d.md")
        )

    async def append_to_memory(
        self,
        content: str,
        date: datetime.date | None = None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        workspace = self._get_user_workspace(user_id)
        if date is None:
            file_path = workspace / self._GENERAL_FILENAME
        else:
            file_path = workspace / self._MEMORY_SUBDIR / date.strftime("%Y-%m-%d.md")
        await self._append_file(file_path, content)

    async def memory_search(
        self, query: str, limit: int = 10, user_id: uuid.UUID | None = None
    ) -> list[str]:
        workspace = self._get_user_workspace(user_id)
        general_file = workspace / self._GENERAL_FILENAME
        memory_dir = workspace / self._MEMORY_SUBDIR
        results_with_scores = []
        files = [
            general_file,
            *sorted(memory_dir.glob("*.md"), reverse=True),
        ]
        for file_path in files:
            content = await self._read_file(file_path)
            if not content:
                continue
            score = self._calculate_similarity(query, content)
            if score > 0:
                results_with_scores.append((score, content))

        results_with_scores.sort(key=lambda x: x[0], reverse=True)
        return [content for _, content in results_with_scores[:limit]]

    async def rewrite_memory(
        self,
        content: str,
        date: datetime.date | None = None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        workspace = self._get_user_workspace(user_id)
        if date is None:
            file_path = workspace / self._GENERAL_FILENAME
        else:
            file_path = workspace / self._MEMORY_SUBDIR / date.strftime("%Y-%m-%d.md")
        await self._write_file(path=file_path, content=content)

    def _get_user_workspace(self, user_id: uuid.UUID | None = None) -> pathlib.Path:
        if user_id is None:
            workspace = self._workspace
        else:
            workspace = self._workspace / str(user_id)
        workspace.mkdir(parents=True, exist_ok=True)
        memory_dir = workspace / self._MEMORY_SUBDIR
        memory_dir.mkdir(parents=True, exist_ok=True)
        return workspace

    def _calculate_similarity(self, query: str, content: str) -> float:
        matcher = difflib.SequenceMatcher(None, query.lower(), content.lower())
        return matcher.ratio()

    async def _read_file(self, path: pathlib.Path) -> str | None:
        path.touch(exist_ok=True)
        async with aiofiles.open(path, encoding="utf-8") as f:
            return await f.read()

    async def _append_file(self, path: pathlib.Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write("\n\n" + content)

    async def _write_file(self, path: pathlib.Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(content)
