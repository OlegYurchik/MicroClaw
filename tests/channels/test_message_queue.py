"""Tests for message queue batching and concurrency via _enqueue_and_process."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.dto import AgentMessage, DecisionEnum
from microclaw.sessions_storages.filters import MessageFilter
from tests.conftest import _async_gen


@pytest.mark.asyncio
async def test_enqueue_and_process_pops_all_and_calls_batch(base_channel):
    chat_id = 1
    session_id = uuid.uuid4()
    await base_channel._sessions_storage.create_session(session_id)
    base_channel._chat_sessions[chat_id] = session_id

    base_channel._process_batch = AsyncMock()

    msg1 = AgentMessage(role="user", text="hello")
    msg2 = AgentMessage(role="user", text="world")

    await base_channel._enqueue_and_process(
        chat_id=chat_id,
        session_id=session_id,
        new_messages=[msg1, msg2],
        agent=base_channel._agent,
    )

    base_channel._process_batch.assert_awaited_once()
    call_kwargs = base_channel._process_batch.await_args.kwargs
    assert call_kwargs["chat_id"] == chat_id
    assert call_kwargs["session_id"] == session_id
    assert call_kwargs["agent"] == base_channel._agent
    batch = call_kwargs["batch"]
    assert len(batch) == 2
    assert batch[0].text == "hello"
    assert batch[1].text == "world"

    # Messages should be saved to storage
    messages = [
        m
        async for m in base_channel._sessions_storage.get_messages(
            filter=MessageFilter(session_id=session_id)
        )
    ]
    assert len(messages) == 2


@pytest.mark.asyncio
async def test_enqueue_and_process_batches_messages_arriving_during_processing(
    base_channel,
):
    """Second message arrives while first batch is being processed.
    The same processor should pick it up in the next loop iteration."""
    chat_id = 1
    session_id = uuid.uuid4()
    await base_channel._sessions_storage.create_session(session_id)
    base_channel._chat_sessions[chat_id] = session_id

    batches = []
    started = asyncio.Event()
    continue_ = asyncio.Event()

    async def slow_process(chat_id, session_id, agent, batch):
        batches.append([m.text for m in batch])
        if len(batches) == 1:
            started.set()
            await continue_.wait()
            await asyncio.sleep(0.01)

    base_channel._process_batch = slow_process

    msg1 = AgentMessage(role="user", text="first")

    task = asyncio.create_task(
        base_channel._enqueue_and_process(
            chat_id=chat_id,
            session_id=session_id,
            new_messages=[msg1],
            agent=base_channel._agent,
        )
    )

    # Wait until task1 is inside _process_batch
    await asyncio.wait_for(started.wait(), timeout=5.0)

    # Simulate second message arriving from another handler
    msg2 = AgentMessage(role="user", text="second")
    await base_channel._syncer.list_append(
        base_channel._get_chat_queue_key(chat_id),
        msg2.model_dump(mode="json"),
    )

    # Let task1 continue
    continue_.set()

    await asyncio.wait_for(task, timeout=5.0)

    assert len(batches) == 2
    assert batches[0] == ["first"]
    assert batches[1] == ["second"]


@pytest.mark.asyncio
async def test_enqueue_and_process_second_call_waits_for_first(base_channel):
    """A second _enqueue_and_process should block until the first finishes."""
    chat_id = 1
    session_id = uuid.uuid4()
    await base_channel._sessions_storage.create_session(session_id)
    base_channel._chat_sessions[chat_id] = session_id

    call_order = []
    started = asyncio.Event()
    continue_ = asyncio.Event()

    async def slow_process(chat_id, session_id, agent, batch):
        call_order.append("start")
        started.set()
        await continue_.wait()
        await asyncio.sleep(0.01)
        call_order.append("end")

    base_channel._process_batch = slow_process

    msg1 = AgentMessage(role="user", text="hello")
    msg2 = AgentMessage(role="user", text="world")

    task1 = asyncio.create_task(
        base_channel._enqueue_and_process(
            chat_id=chat_id,
            session_id=session_id,
            new_messages=[msg1],
            agent=base_channel._agent,
        )
    )

    # Wait until task1 is inside _process_batch
    await asyncio.wait_for(started.wait(), timeout=5.0)

    # Start task2 while task1 still holds the lock
    task2 = asyncio.create_task(
        base_channel._enqueue_and_process(
            chat_id=chat_id,
            session_id=session_id,
            new_messages=[msg2],
            agent=base_channel._agent,
        )
    )

    # Let task1 continue
    continue_.set()

    await asyncio.wait_for(asyncio.gather(task1, task2), timeout=5.0)

    # Both messages were processed; exact split depends on timing,
    # but we must see at least one complete cycle and no lost messages.
    assert call_order.count("start") in (1, 2)
    assert call_order[-1] == "end"

    messages = [
        m
        async for m in base_channel._sessions_storage.get_messages(
            filter=MessageFilter(session_id=session_id)
        )
    ]
    assert len(messages) == 2


@pytest.mark.asyncio
async def test_enqueue_and_process_parallel_chats_do_not_interfere(base_channel):
    """Different chats should process independently."""
    chat_a = 1
    chat_b = 2
    session_a = uuid.uuid4()
    session_b = uuid.uuid4()
    await base_channel._sessions_storage.create_session(session_a)
    await base_channel._sessions_storage.create_session(session_b)
    base_channel._chat_sessions[chat_a] = session_a
    base_channel._chat_sessions[chat_b] = session_b

    # Avoid hitting a real LLM inside _process_batch → agent.ask
    base_channel._agent.has_pending_interrupt = AsyncMock(return_value=False)
    base_channel._agent.ask = MagicMock(return_value=_async_gen([]))

    await asyncio.gather(
        base_channel._enqueue_and_process(
            chat_id=chat_a,
            session_id=session_a,
            new_messages=[AgentMessage(role="user", text="a1")],
            agent=base_channel._agent,
        ),
        base_channel._enqueue_and_process(
            chat_id=chat_b,
            session_id=session_b,
            new_messages=[AgentMessage(role="user", text="b1")],
            agent=base_channel._agent,
        ),
    )

    messages_a = [
        m
        async for m in base_channel._sessions_storage.get_messages(
            filter=MessageFilter(session_id=session_a)
        )
    ]
    messages_b = [
        m
        async for m in base_channel._sessions_storage.get_messages(
            filter=MessageFilter(session_id=session_b)
        )
    ]
    assert len(messages_a) == 1
    assert messages_a[0].text == "a1"
    assert len(messages_b) == 1
    assert messages_b[0].text == "b1"


@pytest.mark.asyncio
async def test_reset_clears_message_queue(base_channel):
    """Simulate /reset: drain queue before creating new session."""
    chat_id = 1
    session_id = uuid.uuid4()
    await base_channel._sessions_storage.create_session(session_id)
    base_channel._chat_sessions[chat_id] = session_id

    # Pre-fill queue with a stale message
    queue_key = base_channel._get_chat_queue_key(chat_id)
    stale = AgentMessage(role="user", text="stale")
    await base_channel._syncer.list_append(queue_key, stale.model_dump(mode="json"))

    # Drain queue (simulating handle_new_session behavior)
    await base_channel._syncer.list_pop_all(queue_key)

    # Ensure queue is empty
    drained = await base_channel._syncer.list_pop_all(queue_key)
    assert drained == []


@pytest.mark.asyncio
async def test_enqueue_and_process_skips_invalid_queued_messages(base_channel):
    """A corrupted queued message should not kill the entire batch."""
    chat_id = 1
    session_id = uuid.uuid4()
    await base_channel._sessions_storage.create_session(session_id)
    base_channel._chat_sessions[chat_id] = session_id

    queue_key = base_channel._get_chat_queue_key(chat_id)
    await base_channel._syncer.list_append(queue_key, {"bad": "data"})
    valid = AgentMessage(role="user", text="valid")
    await base_channel._syncer.list_append(queue_key, valid.model_dump(mode="json"))

    base_channel._process_batch = AsyncMock()

    await base_channel._enqueue_and_process(
        chat_id=chat_id,
        session_id=session_id,
        new_messages=[],
        agent=base_channel._agent,
    )

    base_channel._process_batch.assert_awaited_once()
    batch = base_channel._process_batch.await_args.kwargs["batch"]
    assert len(batch) == 1
    assert batch[0].text == "valid"


@pytest.mark.asyncio
async def test_start_conversation_with_interrupt_uses_resume_then_ask(
    base_channel,
):
    """If has_pending_interrupt is True, batch goes through resume_after_confirmation.
    If more messages are queued afterward, they go through ask."""
    session_id = uuid.uuid4()
    await base_channel._sessions_storage.create_session(session_id)
    base_channel._chat_sessions[1] = session_id

    base_channel._agent.has_pending_interrupt = AsyncMock(
        side_effect=[True, False]
    )
    base_channel._agent.ask = MagicMock(return_value=_async_gen([]))
    base_channel._agent.resume_after_confirmation = MagicMock(
        return_value=_async_gen([])
    )

    await base_channel.start_conversation(
        session_id=session_id,
        channel_internal_id=1,
        new_messages=[AgentMessage(role="user", text="first")],
    )

    base_channel._agent.resume_after_confirmation.assert_called_once()
    call_kwargs = base_channel._agent.resume_after_confirmation.call_args.kwargs
    assert call_kwargs["decision"] == DecisionEnum.REJECT
    assert len(call_kwargs["new_messages"]) == 1
    assert call_kwargs["new_messages"][0].text == "first"

    # ask should NOT be called because there was only one batch
    base_channel._agent.ask.assert_not_called()


@pytest.mark.asyncio
async def test_start_conversation_uses_ask_when_no_interrupt(base_channel):
    session_id = uuid.uuid4()
    await base_channel._sessions_storage.create_session(session_id)
    base_channel._chat_sessions[1] = session_id

    base_channel._agent.has_pending_interrupt = AsyncMock(return_value=False)
    base_channel._agent.ask = MagicMock(return_value=_async_gen([]))
    base_channel._agent.resume_after_confirmation = MagicMock(
        return_value=_async_gen([])
    )

    await base_channel.start_conversation(
        session_id=session_id,
        channel_internal_id=1,
        new_messages=[AgentMessage(role="user", text="hello")],
    )

    base_channel._agent.ask.assert_called_once()
    base_channel._agent.resume_after_confirmation.assert_not_called()
