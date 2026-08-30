import pytest

from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.dynamic_loader.toolkit import DynamicLoaderToolKit


@pytest.fixture
def settings():
    return ToolKitSettings(
        path="microclaw.toolkits.dynamic_loader.toolkit.DynamicLoaderToolKit",
        args={"toolkits": {}},
    )


class TestListToolkits:
    @pytest.mark.asyncio
    async def test_empty_when_no_toolkits(self, settings):
        toolkit = DynamicLoaderToolKit(key="loader", settings=settings)
        result = await toolkit.list_toolkits()
        assert result == []


class TestLoadTools:
    @pytest.mark.asyncio
    async def test_raises_when_toolkit_not_configured(self, settings):
        toolkit = DynamicLoaderToolKit(key="loader", settings=settings)
        with pytest.raises(ValueError, match="not found in available toolkits"):
            await toolkit.load_tools("nonexistent")


class TestCallTool:
    @pytest.mark.asyncio
    async def test_raises_when_toolkit_not_configured(self, settings):
        toolkit = DynamicLoaderToolKit(key="loader", settings=settings)
        with pytest.raises(ValueError, match="not found in available toolkits"):
            await toolkit.call_tool("nonexistent", "some_tool")
