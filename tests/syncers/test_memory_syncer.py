import asyncio

import pytest

from microclaw.syncers.memory.settings import MemorySyncerSettings
from microclaw.syncers.memory.syncer import MemorySyncer


@pytest.fixture
def memory_syncer() -> MemorySyncer:
    return MemorySyncer(settings=MemorySyncerSettings())


@pytest.mark.asyncio
async def test_list_append_and_pop_all(memory_syncer):
    await memory_syncer.list_append("key1", "a")
    await memory_syncer.list_append("key1", "b")
    await memory_syncer.list_append("key1", "c")

    result = await memory_syncer.list_pop_all("key1")
    assert result == ["a", "b", "c"]

    second = await memory_syncer.list_pop_all("key1")
    assert second == []


@pytest.mark.asyncio
async def test_list_pop_all_empty_key(memory_syncer):
    result = await memory_syncer.list_pop_all("nonexistent")
    assert result == []


@pytest.mark.asyncio
async def test_list_append_isolated_keys(memory_syncer):
    await memory_syncer.list_append("k1", 1)
    await memory_syncer.list_append("k2", 2)

    assert await memory_syncer.list_pop_all("k1") == [1]
    assert await memory_syncer.list_pop_all("k2") == [2]


@pytest.mark.asyncio
async def test_list_append_with_dict_values(memory_syncer):
    value = {"role": "user", "text": "hello"}
    await memory_syncer.list_append("queue", value)

    result = await memory_syncer.list_pop_all("queue")
    assert result == [{"role": "user", "text": "hello"}]


@pytest.mark.asyncio
async def test_set_if_not_exists_returns_true_on_first_call(memory_syncer):
    result = await memory_syncer.set_if_not_exists("lock", True)
    assert result is True
    assert await memory_syncer.get("lock") is True


@pytest.mark.asyncio
async def test_set_if_not_exists_returns_false_when_key_exists(memory_syncer):
    await memory_syncer.set("lock", True)
    result = await memory_syncer.set_if_not_exists("lock", False)
    assert result is False
    assert await memory_syncer.get("lock") is True


@pytest.mark.asyncio
async def test_set_if_not_exists_is_atomic(memory_syncer):
    results = []

    async def acquire():
        result = await memory_syncer.set_if_not_exists("lock", True)
        results.append(result)

    await asyncio.gather(*[acquire() for _ in range(10)])
    assert sum(results) == 1
    assert sum(not r for r in results) == 9


@pytest.mark.asyncio
async def test_set_if_not_exists_overwrites_expired_key(memory_syncer):
    await memory_syncer.set("lock", True, ttl=0)
    await asyncio.sleep(0.01)
    result = await memory_syncer.set_if_not_exists("lock", False)
    assert result is True
    assert await memory_syncer.get("lock") is False


@pytest.mark.asyncio
async def test_wait_delete_returns_immediately_when_key_missing(memory_syncer):
    result = await memory_syncer.wait_delete("missing", timeout=1)
    assert result is True


@pytest.mark.asyncio
async def test_wait_delete_wakes_on_delete(memory_syncer):
    await memory_syncer.set("key", "value")

    async def deleter():
        await asyncio.sleep(0.01)
        await memory_syncer.delete("key")

    task = asyncio.create_task(deleter())
    result = await memory_syncer.wait_delete("key", timeout=1)
    await task
    assert result is True


@pytest.mark.asyncio
async def test_wait_delete_times_out(memory_syncer):
    await memory_syncer.set("key", "value")
    result = await memory_syncer.wait_delete("key", timeout=0.01)
    assert result is False


@pytest.mark.asyncio
async def test_wait_delete_expired_key_returns_immediately(memory_syncer):
    await memory_syncer.set("key", "value", ttl=0)
    await asyncio.sleep(0.01)
    result = await memory_syncer.wait_delete("key", timeout=1)
    assert result is True
