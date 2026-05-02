import tempfile
from contextlib import asynccontextmanager
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from aiodav import Client

from microclaw.toolkits.base import BaseToolKit, tool
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.exceptions import UserDeniedAction
from .dto import File, Directory, WebDAVObject
from .settings import WebDAVSettings


class WebDAVToolKit(BaseToolKit[WebDAVSettings]):

    @asynccontextmanager
    async def _create_client(self):
        """Создает новый клиент WebDAV."""
        client = Client(
            hostname=self.settings.url,
            login=self.settings.username,
            password=self.settings.password,
            insecure=not self.settings.verify_ssl,
        )
        try:
            yield client
        finally:
            await client.close()

    @tool
    async def list_files(self, path: str = "/") -> list[WebDAVObject]:
        """
        List files and directories in a WebDAV folder.

        Args:
            path: Path to the directory (optional, uses default_path if not specified)

        Returns:
            List of file and directories with metadata (path, name, size, last_modified, etag)
        """
        path = path.lstrip("/").rstrip("/")

        async with self._create_client() as client:
            items = await client.list(path or "/", get_info=True)
        
        return [
            self._parse_item_info(parent_path=path, item_info=item_info)
            for item_info in items[1:]
        ]

    @tool
    async def get_file(self, path: str) -> File:
        """
        Get information about a file from WebDAV server.

        Args:
            path: Path to the file on WebDAV server

        Returns:
            File object containing file metadata (path, name, size, last_modified, etag)
        """
        path = path.lstrip("/")

        async with self._create_client() as client:
            items = await client.list(path, get_info=True)
        item_info = items[0]
        parent_path = "/".join(path.split("/")[:-1])
        return self._parse_item_info(parent_path=parent_path, item_info=item_info)

    @tool
    async def download_file(self, path: str, local_path: str) -> None:
        """
        Download a file from WebDAV server to local storage.

        Args:
            path: Path to the file on WebDAV server
            local_path: Local path where the file will be saved
        """
        async with self._create_client() as client:
            await client.download_file(path, local_path)

    @tool
    async def upload_file(self, path: str, local_path: str) -> None:
        """
        Upload a file to WebDAV server.

        Args:
            path: Path where the file will be saved on WebDAV server
            local_path: Local path of the file to upload
        """
        self._check_path_access(path)
        if self.settings.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations are disabled")
        if self.settings.write_mode is PermissionModeEnum.REQUEST:
            if not await self.request_confirmation(
                f"Upload file '{local_path}' to WebDAV path '{path}'?"
            ):
                raise UserDeniedAction()

        async with self._create_client() as client:
            await client.upload_file(path, local_path)

    @tool
    async def create_file_with_content(self, path: str, content: bytes) -> None:
        """
        Create a file on WebDAV server with binary content from memory.

        Args:
            path: Path where the file will be created on WebDAV server
            content: Binary content to write to the file
        """
        path = path.lstrip("/")
        self._check_path_access(path)
        if self.settings.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations are disabled")

        if self.settings.write_mode is PermissionModeEnum.REQUEST:
            if not await self.request_confirmation(
                f"Create file at WebDAV path '{path}' with {len(content)} bytes of content?"
            ):
                raise UserDeniedAction()

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            async with self._create_client() as client:
                await client.upload_file(path, temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @tool
    async def delete_file(self, path: str) -> None:
        """
        Delete a file from WebDAV server.

        Args:
            path: Path to the file to delete
        """
        self._check_path_access(path)
        if self.settings.write_mode is PermissionModeEnum.DENY:
            raise PermissionError("Write operations are disabled")

        if self.settings.write_mode is PermissionModeEnum.REQUEST:
            if not await self.request_confirmation(
                f"Delete file at WebDAV path '{path}'?"
            ):
                raise UserDeniedAction()

        async with self._create_client() as client:
            await client.delete(path)

    def _check_path_access(self, path: str) -> None:
        if self.settings.allowed_paths is None:
            return

        normalized_path = path.lstrip("/").rstrip("/")
        for allowed_path in self.settings.allowed_paths:
            normalized_allowed = allowed_path.lstrip("/").rstrip("/")
            if normalized_path == normalized_allowed or normalized_path.startswith(normalized_allowed + "/"):
                return

        raise PermissionError(f"Access denied to path: {path}")

    @staticmethod
    def _parse_item_info(parent_path: str, item_info: dict[str, Any]) -> WebDAVObject:
        item_name = item_info["path"].rstrip("/").split("/")[-1]
        item_path = parent_path + "/" + item_name
        item_last_modified = parsedate_to_datetime(item_info["modified"])
        if item_info["isdir"]:
            return Directory(
                path=item_path,
                name=item_name,
                last_modified=item_last_modified,
            )
        return File(
            path=item_path,
            name=item_name,
            last_modified=item_last_modified,
            size=int(item_info["size"]) if item_info.get("size") is not None else None,
            etag=item_info.get("etag"),
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False
