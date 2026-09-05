"""Tests for AgentCronTask execution flow and session handling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from microclaw.cron.settings import CronTaskSettings
from microclaw.cron.tasks.agent import AgentCronTask
from microclaw.dto import AgentMessage, User
from microclaw.sessions_storages.dto import SessionCreate
from microclaw.sessions_storages.filters import MessageFilter
from microclaw.users_storages.dto import UserCreate
from microclaw.users_storages.filters import UserChannelFilter, UserFilter
from microclaw.users_storages.utils import attach_session_to_user


def _async_gen(items):
    async def _gen():
        for item in items:
            yield item

    return _gen()


def _make_cron_task(resolver, base_channel, agent, **kwargs):
    resolver.resolve_channels = AsyncMock(return_value={"tui": base_channel})
    resolver.resolve_agents = AsyncMock(return_value={"default": agent})
    settings = CronTaskSettings(
        path="microclaw.cron.tasks.agent.AgentCronTask",
        cron="0 4 * * *",
        args=kwargs,
    )
    return AgentCronTask(
        key="morning_briefing",
        settings=settings,
        resolver=resolver,
    )


@pytest.mark.asyncio
async def test_cron_task_with_channel_creates_user_and_session(
    resolver: AsyncMock,
    base_channel,
    users_storage,
    agent,
):
    """Cron task should create a user, attach a fresh session, and save the message."""
    agent_cron_task = _make_cron_task(
        resolver,
        base_channel,
        agent,
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
    from microclaw.users_storages.filters import UserChannelFilter

    user = None
    async for channel in users_storage.get_user_channels(
        filter_=UserChannelFilter(channel_key={"tui"}, channel_internal_id={"tui"})
    ):
        user = await users_storage.get_user(
            filter_=UserFilter(id={channel.user_id})
        )
        break
    assert user is not None
    assert isinstance(user, User)

    # Session should be created and attached
    session_id = None
    async for channel in users_storage.get_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"tui"},
            channel_internal_id={"tui"},
        )
    ):
        session_id = channel.actual_session_id
        break
    assert session_id is not None

    # Message should be in the session storage
    messages = [
        m
        async for m in base_channel._sessions_storage.get_messages(
            filter_=MessageFilter(session_id={session_id})
        )
    ]
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert "Say hello" in (messages[0].text or "")


@pytest.mark.asyncio
async def test_cron_task_reuses_existing_session_when_not_creating_new(
    resolver: AsyncMock,
    base_channel,
    users_storage,
    sessions_storage,
    agent,
):
    """With create_new_session=False the task must use the current session."""
    agent_cron_task = _make_cron_task(
        resolver,
        base_channel,
        agent,
        task="Daily check",
        channel="tui",
        channel_internal_id="tui",
        create_new_session=False,
    )
    await agent_cron_task.do_before()

    # Pre-create user + session + attach
    user = await users_storage.create_user(data=UserCreate())
    existing_session = uuid.uuid4()
    await sessions_storage.create_session(
        data=SessionCreate(id=existing_session, channel_key="tui", channel_internal_id="tui")
    )
    await attach_session_to_user(
        storage=users_storage,
        user_id=user.id,
        session_id=existing_session,
        channel_key="tui",
        channel_internal_id="tui",
    )
    agent_cron_task._agent.ask = MagicMock(return_value=_async_gen([]))

    await agent_cron_task.execute()

    session_id = None
    async for channel in users_storage.get_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"tui"},
            channel_internal_id={"tui"},
        )
    ):
        session_id = channel.actual_session_id
        break
    assert session_id == existing_session

    messages = [
        m
        async for m in sessions_storage.get_messages(
            filter_=MessageFilter(session_id={existing_session})
        )
    ]
    assert len(messages) == 1
    assert "Daily check" in (messages[0].text or "")


@pytest.mark.asyncio
async def test_cron_task_without_channel_calls_agent_ask(
    resolver: AsyncMock,
    agent,
):
    """When no channel is configured the task should call agent.ask directly."""
    agent_cron_task = _make_cron_task(
        resolver,
        MagicMock(),  # base_channel not used
        agent,
        task="Cleanup",
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
    resolver: AsyncMock,
    base_channel,
    users_storage,
    sessions_storage,
    agent,
):
    """Race-condition safety:

    If cron task adds a message with an explicit session_id while a concurrent
    reset (simulated here) happens, the cron message must stay in the session
    it created, and the later concurrent message must use whatever session is
    resolved *inside* the lock.
    """
    agent_cron_task = _make_cron_task(
        resolver,
        base_channel,
        agent,
        task="Morning briefing",
        channel="tui",
        channel_internal_id="tui",
        create_new_session=True,
    )
    await agent_cron_task.do_before()

    # Pre-create user so both sides see the same one
    user = await users_storage.create_user(data=UserCreate())
    await attach_session_to_user(
        storage=users_storage,
        user_id=user.id,
        session_id=uuid.uuid4(),
        channel_key="tui",
        channel_internal_id="tui",
    )

    # -- Make _process_batch slow so the first call holds the lock --
    batch_started = asyncio.Event()

    async def slow_process_batch(chat_id, session_id, agent, batch, **kwargs):
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
    await sessions_storage.create_session(
        data=SessionCreate(id=second_session, channel_key="tui", channel_internal_id="tui")
    )

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
    cron_session_id = None
    async for channel in users_storage.get_user_channels(
        filter_=UserChannelFilter(
            user_id={user.id},
            channel_key={"tui"},
            channel_internal_id={"tui"},
        )
    ):
        cron_session_id = channel.actual_session_id
        break

    # The cron session should contain the cron message
    cron_messages = [
        m
        async for m in sessions_storage.get_messages(
            filter_=MessageFilter(session_id={cron_session_id})
        )
    ]
    assert len(cron_messages) == 1
    assert "Morning briefing" in (cron_messages[0].text or "")

    # The second (normal) message should be in second_session
    normal_messages = [
        m
        async for m in sessions_storage.get_messages(
            filter_=MessageFilter(session_id={second_session})
        )
    ]
    assert len(normal_messages) == 1
    assert normal_messages[0].text == "Normal message"


@pytest.mark.asyncio
async def test_cron_task_process_batch_failure_propagates(
    resolver: AsyncMock,
    base_channel,
    agent,
):
    """If _process_batch raises, the exception must propagate up."""
    agent_cron_task = _make_cron_task(
        resolver,
        base_channel,
        agent,
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
