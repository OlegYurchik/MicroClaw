"""Tests for Agent interrupt/resume public API."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from microclaw.agents.agent import Agent
from microclaw.dto import DecisionEnum


# ---------------------------------------------------------------------------
# has_pending_interrupt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_has_pending_interrupt_true(make_agent, toolkit):
    agent: Agent = make_agent(toolkits={"tools": toolkit}, client=MagicMock())
    session_id = uuid.uuid4()

    mock_graph = MagicMock()
    mock_graph.aget_state = AsyncMock(
        return_value=MagicMock(interrupts=[MagicMock()])
    )

    with patch.object(agent, "_create_agent", new=AsyncMock(return_value=mock_graph)):
        result = await agent.has_pending_interrupt(session_id)

    assert result is True


@pytest.mark.asyncio
async def test_has_pending_interrupt_false(make_agent, toolkit):
    agent: Agent = make_agent(toolkits={"tools": toolkit}, client=MagicMock())
    session_id = uuid.uuid4()

    mock_graph = MagicMock()
    mock_graph.aget_state = AsyncMock(return_value=MagicMock(interrupts=[]))

    with patch.object(agent, "_create_agent", new=AsyncMock(return_value=mock_graph)):
        result = await agent.has_pending_interrupt(session_id)

    assert result is False


# ---------------------------------------------------------------------------
# resume_after_confirmation preserves checkpoint (vs ask which deletes it)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_after_confirmation_preserves_checkpoint(make_agent, toolkit):
    """resume_after_confirmation must NOT delete the checkpointer thread,
    unlike ask() which clears it before starting."""
    agent: Agent = make_agent(toolkits={"tools": toolkit}, client=MagicMock())
    session_id = uuid.uuid4()

    mock_graph = MagicMock()
    mock_graph.astream_events = MagicMock(return_value=_empty_async_gen())

    with (
        patch.object(agent._checkpointer, "adelete_thread", new_callable=AsyncMock) as mock_delete,
        patch.object(agent, "_create_agent", new=AsyncMock(return_value=mock_graph)),
    ):
        _ = [
            msg async for msg in agent.resume_after_confirmation(
                session_id=session_id,
                decision=DecisionEnum.APPROVE,
            )
        ]

    mock_delete.assert_not_awaited()


async def _empty_async_gen():
    """Empty async generator for mocking astream_events."""
    if False:
        yield
