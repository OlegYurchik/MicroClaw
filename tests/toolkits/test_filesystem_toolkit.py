import pytest

from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.filesystem.dto import FilesystemItemType
from microclaw.toolkits.filesystem.toolkit import FileSystemToolKit


class TestListDirectory:
    @pytest.mark.asyncio
    async def test_list_directory_success(self, tmp_path):
        settings = ToolKitSettings(
            path="microclaw.toolkits.filesystem.toolkit.FileSystemToolKit",
            args={
                "directories": [str(tmp_path)],
                "write_mode": "allow",
            },
        )
        toolkit = FileSystemToolKit(key="fs", settings=settings)

        (tmp_path / "file1.txt").write_text("hello")
        (tmp_path / "subdir").mkdir()

        result = await toolkit.list_directory(str(tmp_path))

        assert len(result) == 2
        names = {item.name for item in result}
        assert names == {"file1.txt", "subdir"}

        file_item = next(item for item in result if item.name == "file1.txt")
        assert file_item.type == FilesystemItemType.FILE
        assert file_item.size == 5

        dir_item = next(item for item in result if item.name == "subdir")
        assert dir_item.type == FilesystemItemType.DIRECTORY

    @pytest.mark.asyncio
    async def test_list_directory_not_found(self, tmp_path):
        settings = ToolKitSettings(
            path="microclaw.toolkits.filesystem.toolkit.FileSystemToolKit",
            args={
                "directories": [str(tmp_path)],
                "write_mode": "allow",
            },
        )
        toolkit = FileSystemToolKit(key="fs", settings=settings)

        with pytest.raises(FileNotFoundError):
            await toolkit.list_directory(str(tmp_path / "nonexistent"))

    @pytest.mark.asyncio
    async def test_list_directory_not_a_directory(self, tmp_path):
        settings = ToolKitSettings(
            path="microclaw.toolkits.filesystem.toolkit.FileSystemToolKit",
            args={
                "directories": [str(tmp_path)],
                "write_mode": "allow",
            },
        )
        toolkit = FileSystemToolKit(key="fs", settings=settings)

        (tmp_path / "file.txt").write_text("content")

        with pytest.raises(NotADirectoryError):
            await toolkit.list_directory(str(tmp_path / "file.txt"))

    @pytest.mark.asyncio
    async def test_list_directory_path_outside_allowed(self, tmp_path):
        settings = ToolKitSettings(
            path="microclaw.toolkits.filesystem.toolkit.FileSystemToolKit",
            args={
                "directories": [str(tmp_path)],
                "write_mode": "allow",
            },
        )
        toolkit = FileSystemToolKit(key="fs", settings=settings)

        outside = tmp_path.parent

        with pytest.raises(PermissionError):
            await toolkit.list_directory(str(outside))


class TestReadFile:
    @pytest.mark.asyncio
    async def test_read_file_success(self, tmp_path):
        settings = ToolKitSettings(
            path="microclaw.toolkits.filesystem.toolkit.FileSystemToolKit",
            args={
                "directories": [str(tmp_path)],
                "write_mode": "allow",
            },
        )
        toolkit = FileSystemToolKit(key="fs", settings=settings)

        (tmp_path / "file.txt").write_text("hello world")

        result = await toolkit.read_file(str(tmp_path / "file.txt"))

        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, tmp_path):
        settings = ToolKitSettings(
            path="microclaw.toolkits.filesystem.toolkit.FileSystemToolKit",
            args={
                "directories": [str(tmp_path)],
                "write_mode": "allow",
            },
        )
        toolkit = FileSystemToolKit(key="fs", settings=settings)

        with pytest.raises(FileNotFoundError):
            await toolkit.read_file(str(tmp_path / "nonexistent.txt"))

    @pytest.mark.asyncio
    async def test_read_file_is_directory(self, tmp_path):
        settings = ToolKitSettings(
            path="microclaw.toolkits.filesystem.toolkit.FileSystemToolKit",
            args={
                "directories": [str(tmp_path)],
                "write_mode": "allow",
            },
        )
        toolkit = FileSystemToolKit(key="fs", settings=settings)

        (tmp_path / "subdir").mkdir()

        with pytest.raises(ValueError):
            await toolkit.read_file(str(tmp_path / "subdir"))


class TestWriteFile:
    @pytest.mark.asyncio
    async def test_write_file_success(self, tmp_path):
        settings = ToolKitSettings(
            path="microclaw.toolkits.filesystem.toolkit.FileSystemToolKit",
            args={
                "directories": [str(tmp_path)],
                "write_mode": "allow",
            },
        )
        toolkit = FileSystemToolKit(key="fs", settings=settings)

        await toolkit.write_file(str(tmp_path / "file.txt"), "hello")

        assert (tmp_path / "file.txt").read_text() == "hello"

    @pytest.mark.asyncio
    async def test_write_file_denied(self, tmp_path):
        settings = ToolKitSettings(
            path="microclaw.toolkits.filesystem.toolkit.FileSystemToolKit",
            args={
                "directories": [str(tmp_path)],
                "write_mode": "deny",
            },
        )
        toolkit = FileSystemToolKit(key="fs", settings=settings)

        with pytest.raises(PermissionError):
            await toolkit.write_file(str(tmp_path / "file.txt"), "hello")
