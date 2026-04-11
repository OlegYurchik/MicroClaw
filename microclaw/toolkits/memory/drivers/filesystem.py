import datetime
import difflib
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
        self._general_memory_file = self._workspace / "MEMORY.md"

    async def get_memory(self, date: datetime.date | None = None) -> str | None:
        if date is None:
            return await self._read_file(self._general_memory_file)
        filename = date.strftime("%Y-%m-%d.md")
        return await self._read_file(self._memory_dir / filename)

    async def append_to_memory(self, content: str, date: datetime.date | None = None) -> None:
        file_path = self._general_memory_file
        if date is not None:
            file_path = self._memory_dir / date.strftime("%Y-%m-%d.md")

        await self._append_file(file_path, content)

    async def memory_search(self, query: str, limit: int = 10) -> list[str]:
        results_with_scores = []
        files = [
            self._general_memory_file,
            *sorted(self._memory_dir.glob("*.md"), reverse=True),
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

    async def rewrite_memory(self, content: str, date: datetime.date | None = None):
        file_path = self._general_memory_file
        if date is not None:
            file_path = self._memory_dir / date.strftime("%Y-%m-%d.md")

        await self._write_file(path=file_path, content=content)

    def _calculate_similarity(self, query: str, content: str) -> float:
        matcher = difflib.SequenceMatcher(None, query.lower(), content.lower())
        return matcher.ratio()

    async def _read_file(self, path: pathlib.Path) -> str | None:
        path.touch(exist_ok=True)
        return path.read_text(encoding="utf-8")

    async def _append_file(self, path: pathlib.Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write("\n\n" + content)

    async def _write_file(self, path: pathlib.Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write(content)
