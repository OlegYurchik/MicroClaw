import pathlib
from typing import Any

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction
from .dto import DirectoryInfo, FilesystemItemType
from .settings import FileSystemToolKitSettings


class FileSystemToolKit(BaseToolKit[FileSystemToolKitSettings]):
    """Tools for managing files and directories on the local filesystem."""

    def __init__(self, key: str, settings: FileSystemToolKitSettings):
        super().__init__(key=key, settings=settings)

        self._allowed_paths = [
            pathlib.Path(directory).resolve()
            for directory in self._settings.directories
        ]

    def _validate_path(self, path_str: str) -> pathlib.Path:
        path = pathlib.Path(path_str).resolve()

        for allowed_path in self._allowed_paths:
            try:
                path.relative_to(allowed_path)
                return path
            except ValueError:
                continue

        raise PermissionError(
            f"Path '{path_str}' is not within allowed directories: {self._settings.directories}"
        )

    @tool
    async def list_directory(self, path: str = ".") -> list[DirectoryInfo]:
        """
        List files and directories in the specified path.

        Args:
            path: Path to the directory to list (relative to allowed directories)

        Returns:
            List of DirectoryInfo objects with file/directory information
        """
        validated_path = self._validate_path(path)

        if not validated_path.exists():
            raise FileNotFoundError(f"Path '{path}' does not exist")

        if not validated_path.is_dir():
            raise NotADirectoryError(f"Path '{path}' is not a directory")

        result = []
        for item in validated_path.iterdir():
            stat = item.stat()
            result.append(
                DirectoryInfo(
                    name=item.name,
                    type=FilesystemItemType.DIRECTORY if item.is_dir() else FilesystemItemType.FILE,
                    size=stat.st_size if item.is_file() else None,
                    modified=stat.st_mtime,
                )
            )

        return result

    @tool
    async def read_file(self, path: str) -> str:
        """
        Read the contents of a file.

        Args:
            path: Path to the file to read (relative to allowed directories)

        Returns:
            File contents as a string
        """
        validated_path = self._validate_path(path)

        if not validated_path.exists():
            raise FileNotFoundError(f"File '{path}' does not exist")

        if not validated_path.is_file():
            raise ValueError(f"Path '{path}' is not a file")

        return validated_path.read_text(encoding="utf-8")

    @tool
    async def write_file(self, path: str, content: str) -> None:
        """
        Write content to a file. Creates parent directories if needed.

        Args:
            path: Path to the file to write (relative to allowed directories)
            content: Content to write to the file
        """

        if self.settings.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("File writing is not allowed")
        if self.settings.write_mode is PermissionModeEnum.REQUEST:
            confirmation_request_text = f"Write content to file '{path}'?"
            if not await self.request_confirmation(confirmation_request_text):
                raise UserDeniedAction()

        validated_path = self._validate_path(path)
        validated_path.parent.mkdir(parents=True, exist_ok=True)
        validated_path.write_text(content, encoding="utf-8")
