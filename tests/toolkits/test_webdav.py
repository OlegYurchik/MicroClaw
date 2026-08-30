from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.enums import PermissionModeEnum
from microclaw.toolkits.webdav.toolkit import WebDAVToolKit


class TestWebDAVToolKit:
    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        client.list = AsyncMock(
            return_value=[
                {
                    "path": "/dir/",
                    "isdir": True,
                    "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
                },
                {
                    "path": "/dir/file.txt",
                    "isdir": False,
                    "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
                    "size": "100",
                    "etag": "abc",
                },
            ]
        )

        async def _chunk_iter():
            yield b"hello"

        client._execute_request = AsyncMock(
            return_value=AsyncMock(
                content=MagicMock(
                    iter_chunked=MagicMock(return_value=_chunk_iter())
                )
            )
        )
        client._chunk_size = 8192
        client.upload_file = AsyncMock()
        client.delete = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def toolkit(self, mock_client):
        settings = ToolKitSettings(
            path="microclaw.toolkits.webdav.toolkit.WebDAVToolKit",
            args={"url": "http://test", "username": "u", "password": "p"},
        )
        return WebDAVToolKit(
            key="webdav", settings=settings, client_factory=lambda: mock_client
        )

    @pytest.mark.asyncio
    async def test_list_files_success(self, toolkit):
        result = await toolkit.list_files(path="/dir")
        assert len(result) == 1
        assert result[0].name == "file.txt"

    @pytest.mark.asyncio
    async def test_get_file_success(self, toolkit, mock_client):
        mock_client.list = AsyncMock(
            return_value=[
                {
                    "path": "/dir/file.txt",
                    "isdir": False,
                    "modified": "Mon, 01 Jan 2024 00:00:00 GMT",
                    "size": "100",
                    "etag": "abc",
                },
            ]
        )
        result = await toolkit.get_file(path="/dir/file.txt")
        assert result.name == "file.txt"
        assert result.size == 100

    @pytest.mark.asyncio
    async def test_download_file_success(self, toolkit, mock_client, tmp_path):
        local_file = tmp_path / "file.txt"
        await toolkit.download_file(path="/dir/file.txt", local_path=str(local_file))
        mock_client._execute_request.assert_awaited_once_with(
            action="download", path="/dir/file.txt"
        )
        assert local_file.read_bytes() == b"hello"

    @pytest.mark.asyncio
    async def test_download_file_with_cyrillic_and_spaces(
        self, toolkit, mock_client, tmp_path
    ):
        local_file = tmp_path / "downloaded.txt"
        await toolkit.download_file(
            path="/dir/файл с пробелами.txt", local_path=str(local_file)
        )
        mock_client._execute_request.assert_awaited_once_with(
            action="download",
            path="/dir/%D1%84%D0%B0%D0%B9%D0%BB%20%D1%81%20%D0%BF%D1%80%D0%BE%D0%B1%D0%B5%D0%BB%D0%B0%D0%BC%D0%B8.txt",
        )
        assert local_file.read_bytes() == b"hello"

    @pytest.mark.asyncio
    async def test_upload_file_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.upload_file(path="/dir/file.txt", local_path="/tmp/file.txt")

    @pytest.mark.asyncio
    async def test_upload_file_denied(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.DENY
        with pytest.raises(PermissionError):
            await toolkit.upload_file(path="/dir/file.txt", local_path="/tmp/file.txt")

    @pytest.mark.asyncio
    async def test_create_file_with_content_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.create_file_with_content(path="/dir/new.txt", content=b"hello")

    @pytest.mark.asyncio
    async def test_delete_file_success(self, toolkit):
        toolkit.arguments.write_mode = PermissionModeEnum.ALLOW
        await toolkit.delete_file(path="/dir/file.txt")

    @pytest.mark.asyncio
    async def test_delete_file_path_access_denied(self, toolkit):
        toolkit.arguments.allowed_paths = ["/other"]
        with pytest.raises(PermissionError):
            await toolkit.delete_file(path="/dir/file.txt")
