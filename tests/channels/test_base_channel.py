from unittest.mock import AsyncMock, MagicMock

import pytest
import uuid

from microclaw.agents import Agent
from microclaw.dto import AgentMessage, Spending, User
from microclaw.sessions_storages.memory.storage import MemorySessionsStorage
from microclaw.syncers.memory.syncer import MemorySyncer


@pytest.mark.asyncio
async def test_get_agent_for_user_returns_none_when_no_agent_settings(base_channel):
    user = User(id=uuid.uuid4(), agent=None)
    result = await base_channel.get_agent_for_user(user)
    assert result is None


@pytest.mark.asyncio
async def test_get_agent_for_user_caches_resolved_agent(base_channel, resolver):
    user = User(id=uuid.uuid4(), agent={"identity": {"name": "Test"}})
    fake_agent = MagicMock(spec=Agent)
    resolver.resolve_agent = AsyncMock(return_value=fake_agent)
    agent1 = await base_channel.get_agent_for_user(user)
    agent2 = await base_channel.get_agent_for_user(user)
    assert agent1 is agent2 is fake_agent


@pytest.mark.asyncio
async def test_get_agent_for_user_different_users_different_agents(base_channel, resolver):
    fake_a, fake_b = MagicMock(spec=Agent), MagicMock(spec=Agent)
    resolver.resolve_agent = AsyncMock(side_effect=[fake_a, fake_b])
    user1 = User(id=uuid.uuid4(), agent={"identity": {"name": "A"}})
    user2 = User(id=uuid.uuid4(), agent={"identity": {"name": "B"}})
    result_a = await base_channel.get_agent_for_user(user1)
    result_b = await base_channel.get_agent_for_user(user2)
    assert result_a is fake_a
    assert result_b is fake_b


@pytest.mark.parametrize(
    "window,threshold,context_size,expected",
    [
        (None, None, 1000, False),
        (None, 0.8, 1000, False),
        (1000, None, 1000, False),
        (1000, 0.8, 900, True),
        (1000, 0.8, 700, False),
        (1000, 0.8, 800, False),
        (500, 0.5, 251, True),
        (500, 0.5, 250, False),
    ],
)
@pytest.mark.asyncio
async def test_is_context_went_across_threshold_parametrized(
        base_channel,
        sessions_storage,
        window,
        threshold,
        context_size,
        expected,
):
    agent = MagicMock()
    agent.get_model_context_window_size.return_value = window
    agent.get_context_threshold_size.return_value = threshold
    session_id = uuid.uuid4()
    await sessions_storage.create_session(session_id)
    await sessions_storage.add_message(
        session_id,
        AgentMessage(role="user", text="x", spending=Spending(output_tokens=context_size)),
    )
    result = await base_channel.is_context_went_across_threshold(agent=agent, session_id=session_id)
    assert result is expected


@pytest.mark.asyncio
async def test_resolve_confirmation_sets_approved(base_channel, syncer):
    session_id = uuid.uuid4()
    confirmation_id = uuid.uuid4()
    await base_channel.resolve_confirmation(session_id=session_id, confirmation_id=confirmation_id, approved=True)
    stored = await syncer.get(f"confirm:{session_id}:{confirmation_id}")
    assert stored is True


@pytest.mark.asyncio
async def test_reject_all_pending_confirmations(base_channel, syncer):
    session_id = uuid.uuid4()
    confirmations = [
        f"confirm:{session_id}:{uuid.uuid4()}",
        f"confirm:{session_id}:{uuid.uuid4()}",
    ]
    for key in confirmations:
        await syncer.set(key, True)
    await base_channel.reject_all_pending_confirmations(session_id=session_id)
    for key in confirmations:
        assert await syncer.get(key) is False
