from contextlib import asynccontextmanager
from email.utils import parsedate_to_datetime
from typing import Any

from aiodav import Client

from microclaw.toolkits.base import BaseToolKit, tool
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
        async with self._create_client() as client:
            await client.upload_file(path, local_path)

    @tool
    async def delete_file(self, path: str) -> None:
        """
        Delete a file from WebDAV server.

        Args:
            path: Path to the file to delete
        """
        async with self._create_client() as client:
            await client.delete(path)

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
        """Асинхронный вход в контекстный менеджер."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный выход из контекстного менеджера."""
        return False
