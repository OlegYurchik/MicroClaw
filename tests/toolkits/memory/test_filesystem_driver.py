import pytest

from microclaw.toolkits.memory.drivers.filesystem import (
    FilesystemMemoryDriver,
    FilesystemMemoryDriverSettings,
)


class TestGetMemory:
    @pytest.mark.asyncio
    async def test_get_memory_existing(self, tmp_path):
        settings = FilesystemMemoryDriverSettings(workspace=tmp_path)
        driver = FilesystemMemoryDriver(settings=settings)

        await driver.rewrite_memory(content="hello world")

        result = await driver.get_memory()

        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_get_memory_missing(self, tmp_path):
        settings = FilesystemMemoryDriverSettings(workspace=tmp_path)
        driver = FilesystemMemoryDriver(settings=settings)

        result = await driver.get_memory()

        assert result == ""

    @pytest.mark.asyncio
    async def test_get_memory_default_key(self, tmp_path):
        settings = FilesystemMemoryDriverSettings(workspace=tmp_path)
        driver = FilesystemMemoryDriver(settings=settings)

        await driver.rewrite_memory(content="general memory")

        result = await driver.get_memory(date=None)

        assert result == "general memory"
        assert (tmp_path / "MEMORY.md").exists()


class TestAppendToMemory:
    @pytest.mark.asyncio
    async def test_append_to_memory_new_file(self, tmp_path):
        settings = FilesystemMemoryDriverSettings(workspace=tmp_path)
        driver = FilesystemMemoryDriver(settings=settings)

        await driver.append_to_memory(content="first entry")

        assert (tmp_path / "MEMORY.md").read_text() == "\n\nfirst entry"

    @pytest.mark.asyncio
    async def test_append_to_memory_existing(self, tmp_path):
        settings = FilesystemMemoryDriverSettings(workspace=tmp_path)
        driver = FilesystemMemoryDriver(settings=settings)

        await driver.rewrite_memory(content="existing")
        await driver.append_to_memory(content="appended")

        result = await driver.get_memory()

        assert result == "existing\n\nappended"


class TestMemorySearch:
    @pytest.mark.asyncio
    async def test_memory_search_found(self, tmp_path):
        settings = FilesystemMemoryDriverSettings(workspace=tmp_path)
        driver = FilesystemMemoryDriver(settings=settings)

        await driver.rewrite_memory(content="apple banana cherry")

        results = await driver.memory_search(query="banana")

        assert len(results) == 1
        assert "apple banana cherry" in results[0]

    @pytest.mark.asyncio
    async def test_memory_search_not_found(self, tmp_path):
        settings = FilesystemMemoryDriverSettings(workspace=tmp_path)
        driver = FilesystemMemoryDriver(settings=settings)

        results = await driver.memory_search(query="xyz123")

        assert results == []


class TestRewriteMemory:
    @pytest.mark.asyncio
    async def test_rewrite_memory(self, tmp_path):
        settings = FilesystemMemoryDriverSettings(workspace=tmp_path)
        driver = FilesystemMemoryDriver(settings=settings)

        await driver.rewrite_memory(content="old content")
        await driver.rewrite_memory(content="new content")

        result = await driver.get_memory()

        assert result == "new content"
