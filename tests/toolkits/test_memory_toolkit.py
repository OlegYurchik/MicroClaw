from unittest.mock import AsyncMock

import pytest

from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.memory.toolkit import MemorySizeExceeded, MemoryToolKit


@pytest.fixture
def memory_toolkit_settings() -> ToolKitSettings:
    return ToolKitSettings(
        path="microclaw.toolkits.memory.toolkit.MemoryToolKit",
        args={
            "max_memory_tokens": 2000,
            "edit_mode": "allow",
        },
    )


@pytest.fixture
def driver():
    return AsyncMock()


@pytest.mark.asyncio
async def test_get_memory(toolkit_context, memory_toolkit_settings, driver):
    driver.get_memory.return_value = "memory content"

    toolkit = MemoryToolKit(
        key="memory",
        settings=memory_toolkit_settings,
        driver=driver,
    )

    result = await toolkit.get_memory()

    assert result == "memory content"
    driver.get_memory.assert_awaited_once()


@pytest.mark.asyncio
async def test_append_to_memory(toolkit_context, memory_toolkit_settings, driver):
    toolkit = MemoryToolKit(
        key="memory",
        settings=memory_toolkit_settings,
        driver=driver,
    )

    await toolkit.append_to_memory(content="new info")

    driver.append_to_memory.assert_awaited_once()


@pytest.mark.asyncio
async def test_memory_search(toolkit_context, memory_toolkit_settings, driver):
    driver.memory_search.return_value = ["result 1", "result 2"]

    toolkit = MemoryToolKit(
        key="memory",
        settings=memory_toolkit_settings,
        driver=driver,
    )

    result = await toolkit.memory_search(query="test query")

    assert result == ["result 1", "result 2"]
    driver.memory_search.assert_awaited_once_with(
        "test query", 10, user_id=toolkit_context.current_user_accessor.user_id
    )


@pytest.mark.asyncio
async def test_rewrite_memory(toolkit_context, memory_toolkit_settings, driver):
    toolkit = MemoryToolKit(
        key="memory",
        settings=memory_toolkit_settings,
        driver=driver,
    )

    await toolkit.rewrite_memory(content="replacement")

    driver.rewrite_memory.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_memory_default_key(toolkit_context, memory_toolkit_settings, driver):
    driver.get_memory.return_value = "general memory"

    toolkit = MemoryToolKit(
        key="memory",
        settings=memory_toolkit_settings,
        driver=driver,
    )

    result = await toolkit.get_memory()

    assert result == "general memory"
    driver.get_memory.assert_awaited_once_with(
        None, user_id=toolkit_context.current_user_accessor.user_id
    )


@pytest.mark.asyncio
async def test_append_to_memory_denied(
    toolkit_context, memory_toolkit_settings, driver
):
    settings_denied = memory_toolkit_settings.model_copy(
        update={"args": {**memory_toolkit_settings.args, "edit_mode": "deny"}}
    )
    toolkit = MemoryToolKit(
        key="memory",
        settings=settings_denied,
        driver=driver,
    )

    with pytest.raises(PermissionError):
        await toolkit.append_to_memory(content="new info")


@pytest.mark.asyncio
async def test_rewrite_memory_denied(toolkit_context, memory_toolkit_settings, driver):
    settings_denied = memory_toolkit_settings.model_copy(
        update={"args": {**memory_toolkit_settings.args, "edit_mode": "deny"}}
    )
    toolkit = MemoryToolKit(
        key="memory",
        settings=settings_denied,
        driver=driver,
    )

    with pytest.raises(PermissionError):
        await toolkit.rewrite_memory(content="new info")


@pytest.mark.asyncio
async def test_append_to_memory_exceeds_limit(
    toolkit_context, memory_toolkit_settings, driver
):
    driver.get_memory.return_value = "x" * 10000

    toolkit = MemoryToolKit(
        key="memory",
        settings=memory_toolkit_settings,
        driver=driver,
    )

    with pytest.raises(MemorySizeExceeded):
        await toolkit.append_to_memory(content="y" * 10000)


@pytest.mark.asyncio
async def test_get_memory_no_context(driver):
    toolkit = MemoryToolKit(
        key="memory",
        settings=ToolKitSettings(
            path="microclaw.toolkits.memory.toolkit.MemoryToolKit",
            args={"max_memory_tokens": 2000, "edit_mode": "allow"},
        ),
        driver=driver,
    )

    result = await toolkit.get_memory()
    assert result is None


@pytest.mark.asyncio
async def test_memory_search_no_context(driver):
    toolkit = MemoryToolKit(
        key="memory",
        settings=ToolKitSettings(
            path="microclaw.toolkits.memory.toolkit.MemoryToolKit",
            args={"max_memory_tokens": 2000, "edit_mode": "allow"},
        ),
        driver=driver,
    )

    result = await toolkit.memory_search(query="test")
    assert result == []


def test_get_tokens_count_empty():
    toolkit = MemoryToolKit(
        key="memory",
        settings=ToolKitSettings(
            path="microclaw.toolkits.memory.toolkit.MemoryToolKit",
            args={"max_memory_tokens": 2000, "edit_mode": "allow"},
        ),
        driver=AsyncMock(),
    )
    assert toolkit._get_tokens_count("") == 0


def test_get_tokens_count_non_empty():
    toolkit = MemoryToolKit(
        key="memory",
        settings=ToolKitSettings(
            path="microclaw.toolkits.memory.toolkit.MemoryToolKit",
            args={"max_memory_tokens": 2000, "edit_mode": "allow"},
        ),
        driver=AsyncMock(),
    )
    count = toolkit._get_tokens_count("hello world")
    assert count > 0


def test_memory_size_exceeded_general():
    exc = MemorySizeExceeded(max_tokens=100)
    assert "general memory" in str(exc)


def test_memory_size_exceeded_daily():
    import datetime

    exc = MemorySizeExceeded(max_tokens=100, date=datetime.date(2024, 1, 1))
    assert "daily" in str(exc)
