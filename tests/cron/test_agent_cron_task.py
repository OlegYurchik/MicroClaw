"""Tests for AgentCronTask execution flow and session handling."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.cron.settings import CronTaskSettings
from microclaw.cron.tasks.agent import AgentCronTask, AgentCronTaskSettings
from microclaw.dto import AgentMessage, User
from microclaw.sessions_storages.filters import MessageFilter


def _async_gen(items):
    async def _gen():
        for item in items:
            yield item

    return _gen()


@pytest.fixture
def cron_task_settings() -> CronTaskSettings:
    return CronTaskSettings(
        path="microclaw.cron.tasks.agent.AgentCronTask",
        cron="0 4 * * *",
        args={"task": "default"},
    )


@pytest.fixture
def agent_cron_task(
    cron_task_settings: CronTaskSettings,
    resolver: AsyncMock,
    base_channel,
    agent,
):
    resolver.resolve_channels = AsyncMock(return_value={"tui": base_channel})
    resolver.resolve_agents = AsyncMock(return_value={"default": agent})

    task = AgentCronTask(
        key="morning_briefing",
        settings=cron_task_settings,
        resolver=resolver,
    )
    return task


@pytest.mark.asyncio
async def test_cron_task_with_channel_creates_user_and_session(
    agent_cron_task: AgentCronTask,
    base_channel,
    users_storage,
):
    """Cron task should create a user, attach a fresh session, and save the message."""
    agent_cron_task._settings = AgentCronTaskSettings(
        task="Say hello",
        channel="tui",
        channel_internal_id="tui",
        create_new_session=True,
    )
    await agent_cron_task.do_before()

    # Avoid hitting a real LLM inside Agent.ask
    agent_cron_task._agent.ask = MagicMock(return_value=_async_gen([]))

    await agent_cron_task.execute()

    # User should exist for this channel
    user = await users_storage.get_user_by_channel(
        channel_key="tui",
        channel_internal_id="tui",
    )
    assert user is not None
    assert isinstance(user, User)

    # Session should be created and attached
    session_id = await users_storage.get_actual_session(
        user_id=user.id,
        channel_key="tui",
        channel_internal_id="tui",
    )
    assert session_id is not None

    # Message should be in the session storage
    messages = [
        m
        async for m in base_channel._sessions_storage.get_messages(
            filter=MessageFilter(session_id=session_id)
        )
    ]
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert "Say hello" in (messages[0].text or "")


@pytest.mark.asyncio
async def test_cron_task_reuses_existing_session_when_not_creating_new(
    agent_cron_task: AgentCronTask,
    base_channel,
    users_storage,
    sessions_storage,
):
    """With create_new_session=False the task must use the current session."""
    agent_cron_task._settings = AgentCronTaskSettings(
        task="Daily check",
        channel="tui",
        channel_internal_id="tui",
        create_new_session=False,
    )
    await agent_cron_task.do_before()

    # Pre-create user + session + attach
    user = await users_storage.create_user()
    existing_session = uuid.uuid4()
    await sessions_storage.create_session(existing_session)
    await users_storage.attach_session_to_user(
        user_id=user.id,
        session_id=existing_session,
        channel_key="tui",
        channel_internal_id="tui",
    )
    agent_cron_task._agent.ask = MagicMock(return_value=_async_gen([]))

    await agent_cron_task.execute()

    session_id = await users_storage.get_actual_session(
        user_id=user.id,
        channel_key="tui",
        channel_internal_id="tui",
    )
    assert session_id == existing_session

    messages = [
        m
        async for m in sessions_storage.get_messages(
            filter=MessageFilter(session_id=existing_session)
        )
    ]
    assert len(messages) == 1
    assert "Daily check" in (messages[0].text or "")


@pytest.mark.asyncio
async def test_cron_task_without_channel_calls_agent_ask(
    agent_cron_task: AgentCronTask,
):
    """When no channel is configured the task should call agent.ask directly."""
    agent_cron_task._settings = AgentCronTaskSettings(
        task="Cleanup",
        channel=None,
        channel_internal_id=None,
        agent="default",
        create_new_session=True,
    )
    await agent_cron_task.do_before()

    agent_cron_task._agent.ask = MagicMock(return_value=_async_gen([]))

    await agent_cron_task.execute()

    agent_cron_task._agent.ask.assert_called_once()
    call_kwargs = agent_cron_task._agent.ask.call_args.kwargs
    assert call_kwargs.get("stream") is False
    messages = call_kwargs["messages"]
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert "Cleanup" in (messages[0].text or "")


@pytest.mark.asyncio
async def test_cron_session_preserved_under_lock(
    agent_cron_task: AgentCronTask,
    base_channel,
    users_storage,
    sessions_storage,
):
    """Race-condition safety:

    If cron task adds a message with an explicit session_id while a concurrent
    reset (simulated here) happens, the cron message must stay in the session
    it created, and the later concurrent message must use whatever session is
    resolved *inside* the lock.
    """
    agent_cron_task._settings = AgentCronTaskSettings(
        task="Morning briefing",
        channel="tui",
        channel_internal_id="tui",
        create_new_session=True,
    )
    await agent_cron_task.do_before()

    # Pre-create user so both sides see the same one
    user = await users_storage.create_user()
    await users_storage.attach_session_to_user(
        user_id=user.id,
        session_id=uuid.uuid4(),
        channel_key="tui",
        channel_internal_id="tui",
    )

    # -- Make _process_batch slow so the first call holds the lock --
    batch_started = asyncio.Event()

    async def slow_process_batch(chat_id, session_id, agent, batch):
        batch_started.set()
        await asyncio.sleep(0.2)

    base_channel._process_batch = slow_process_batch

    # Start cron; it will create its own session and enter the lock
    cron_task = asyncio.create_task(agent_cron_task.execute())
    await batch_started.wait()

    # While the lock is held by cron, a "normal" message arrives.
    # It must block on the lock and resolve its session only once inside.
    # We replace _resolve_session_for_chat so that after cron releases the
    # lock it returns a DIFFERENT session id.
    second_session = uuid.uuid4()
    await sessions_storage.create_session(second_session)

    base_channel._resolve_session_for_chat = AsyncMock(
        return_value=second_session
    )

    normal_msg = AgentMessage(role="user", text="Normal message")
    normal_task = asyncio.create_task(
        base_channel._enqueue_and_process(
            chat_id="tui",
            new_messages=[normal_msg],
            agent=base_channel._agent,
        )
    )

    await asyncio.gather(cron_task, normal_task)

    # get_actual_session should still return the cron session because
    # second_session was NOT attached to the user.
    cron_session_id = await users_storage.get_actual_session(
        user_id=user.id,
        channel_key="tui",
        channel_internal_id="tui",
    )

    # The cron session should contain the cron message
    cron_messages = [
        m
        async for m in sessions_storage.get_messages(
            filter=MessageFilter(session_id=cron_session_id)
        )
    ]
    assert len(cron_messages) == 1
    assert "Morning briefing" in (cron_messages[0].text or "")

    # The second (normal) message should be in second_session
    normal_messages = [
        m
        async for m in sessions_storage.get_messages(
            filter=MessageFilter(session_id=second_session)
        )
    ]
    assert len(normal_messages) == 1
    assert normal_messages[0].text == "Normal message"


@pytest.mark.asyncio
async def test_cron_task_process_batch_failure_propagates(
    agent_cron_task: AgentCronTask,
    base_channel,
):
    """If _process_batch raises, the exception must propagate up."""
    agent_cron_task._settings = AgentCronTaskSettings(
        task="Crash test",
        channel="tui",
        channel_internal_id="tui",
        create_new_session=True,
    )
    await agent_cron_task.do_before()

    base_channel._process_batch = AsyncMock(
        side_effect=RuntimeError("boom")
    )

    with pytest.raises(RuntimeError, match="boom"):
        await agent_cron_task.execute()

    base_channel._process_batch.assert_awaited()
