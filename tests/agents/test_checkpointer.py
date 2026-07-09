"""Tests for SyncerCheckpointer."""

import pytest

from langgraph.checkpoint.base import CheckpointTuple

from microclaw.agents.checkpointer import SyncerCheckpointer
from microclaw.syncers.memory.settings import MemorySyncerSettings
from microclaw.syncers.memory.syncer import MemorySyncer


@pytest.fixture
def memory_syncer():
    return MemorySyncer(settings=MemorySyncerSettings())


@pytest.fixture
def checkpointer(memory_syncer):
    return SyncerCheckpointer(memory_syncer)


@pytest.mark.asyncio
async def test_put_and_get_tuple_returns_checkpoint_id(checkpointer):
    """aget_tuple must include checkpoint_id in the returned config."""
    config = {"configurable": {"thread_id": "t1", "checkpoint_ns": ""}}
    checkpoint = {
        "v": 1,
        "ts": "2024-01-01T00:00:00",
        "id": "abc-123",
        "channel_values": {"messages": []},
        "channel_versions": {},
        "versions_seen": {},
    }
    metadata = {"step": 0}

    result_config = await checkpointer.aput(config, checkpoint, metadata, {})
    assert result_config["configurable"]["checkpoint_id"] == "abc-123"

    # Fetch without checkpoint_id in query config
    tuple_ = await checkpointer.aget_tuple(config)
    assert tuple_ is not None
    assert tuple_.config["configurable"]["checkpoint_id"] == "abc-123"
    assert tuple_.checkpoint["id"] == "abc-123"


@pytest.mark.asyncio
async def test_get_tuple_with_checkpoint_id(checkpointer):
    """aget_tuple with explicit checkpoint_id must return correct tuple."""
    config = {"configurable": {"thread_id": "t2", "checkpoint_ns": ""}}
    checkpoint = {
        "v": 1,
        "ts": "2024-01-01T00:00:00",
        "id": "def-456",
        "channel_values": {},
        "channel_versions": {},
        "versions_seen": {},
    }
    await checkpointer.aput(config, checkpoint, {"step": 0}, {})

    query_config = {
        "configurable": {"thread_id": "t2", "checkpoint_ns": "", "checkpoint_id": "def-456"}
    }
    tuple_ = await checkpointer.aget_tuple(query_config)
    assert tuple_ is not None
    assert tuple_.checkpoint["id"] == "def-456"


@pytest.mark.asyncio
async def test_pending_writes_roundtrip(checkpointer):
    """aput_writes must be reflected in aget_tuple.pending_writes."""
    config = {"configurable": {"thread_id": "t3", "checkpoint_ns": "", "checkpoint_id": "chk-1"}}
    checkpoint = {
        "v": 1,
        "ts": "2024-01-01T00:00:00",
        "id": "chk-1",
        "channel_values": {},
        "channel_versions": {},
        "versions_seen": {},
    }
    await checkpointer.aput(config, checkpoint, {"step": 0}, {})

    await checkpointer.aput_writes(
        config,
        [("__interrupt__", "interrupt-value")],
        task_id="task-1",
    )

    tuple_ = await checkpointer.aget_tuple(config)
    assert tuple_.pending_writes is not None
    assert len(tuple_.pending_writes) == 1
    task_id, channel, value = tuple_.pending_writes[0]
    assert task_id == "task-1"
    assert channel == "__interrupt__"
    assert value == "interrupt-value"


@pytest.mark.asyncio
async def test_alist_includes_pending_writes(checkpointer):
    """alist must yield CheckpointTuples with pending_writes."""
    config = {"configurable": {"thread_id": "t4", "checkpoint_ns": "", "checkpoint_id": "chk-2"}}
    checkpoint = {
        "v": 1,
        "ts": "2024-01-01T00:00:00",
        "id": "chk-2",
        "channel_values": {},
        "channel_versions": {},
        "versions_seen": {},
    }
    await checkpointer.aput(config, checkpoint, {"step": 0}, {})
    await checkpointer.aput_writes(
        config,
        [("messages", {"content": "hi"})],
        task_id="task-2",
    )

    tuples = [t async for t in checkpointer.alist(config)]
    assert len(tuples) == 1
    assert tuples[0].pending_writes is not None
    assert tuples[0].pending_writes[0][0] == "task-2"


@pytest.mark.asyncio
async def test_delete_thread_removes_checkpoints_and_writes(checkpointer):
    """adelete_thread must clean up both checkpoints and checkpoint_writes."""
    thread_id = "t5"
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": "", "checkpoint_id": "chk-3"}}
    checkpoint = {
        "v": 1,
        "ts": "2024-01-01T00:00:00",
        "id": "chk-3",
        "channel_values": {},
        "channel_versions": {},
        "versions_seen": {},
    }
    await checkpointer.aput(config, checkpoint, {"step": 0}, {})
    await checkpointer.aput_writes(config, [("foo", "bar")], task_id="task-3")

    await checkpointer.adelete_thread(thread_id)

    assert await checkpointer.aget_tuple(config) is None
    keys = await checkpointer._syncer.scan_keys(f"checkpoint_writes:{thread_id}:*")
    assert len(keys) == 0


@pytest.mark.asyncio
async def test_copy_thread_copies_checkpoints_and_writes(checkpointer):
    """acopy_thread must duplicate both checkpoints and checkpoint_writes."""
    source_id = "t6"
    target_id = "t7"
    config = {"configurable": {"thread_id": source_id, "checkpoint_ns": "", "checkpoint_id": "chk-4"}}
    checkpoint = {
        "v": 1,
        "ts": "2024-01-01T00:00:00",
        "id": "chk-4",
        "channel_values": {"x": 1},
        "channel_versions": {},
        "versions_seen": {},
    }
    await checkpointer.aput(config, checkpoint, {"step": 0}, {})
    await checkpointer.aput_writes(config, [("baz", "qux")], task_id="task-4")

    await checkpointer.acopy_thread(source_id, target_id)

    target_config = {"configurable": {"thread_id": target_id, "checkpoint_ns": "", "checkpoint_id": "chk-4"}}
    tuple_ = await checkpointer.aget_tuple(target_config)
    assert tuple_ is not None
    assert tuple_.checkpoint["channel_values"]["x"] == 1
    assert tuple_.pending_writes is not None
    assert len(tuple_.pending_writes) == 1
    assert tuple_.pending_writes[0] == ("task-4", "baz", "qux")
