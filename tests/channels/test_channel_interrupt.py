"""Tests for channel-level interrupt flow (auto-reject on new message)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from microclaw.dto import AgentMessage, DecisionEnum


def _async_gen(items):
    async def _gen():
        for item in items:
            yield item
    return _gen()


@pytest.mark.asyncio
async def test_start_conversation_calls_ask_when_no_pending_interrupt(base_channel):
    """When no pending interrupt exists, start_conversation should call ask()."""
    session_id = uuid.uuid4()
    await base_channel._sessions_storage.create_session(session_id)

    base_channel._agent.has_pending_interrupt = AsyncMock(return_value=False)
    base_channel._agent.ask = MagicMock(return_value=_async_gen([]))
    base_channel._agent.resume_after_confirmation = MagicMock(return_value=_async_gen([]))

    await base_channel.start_conversation(
        session_id=session_id,
        channel_internal_id=1,
        new_messages=[AgentMessage(role="user", text="hello")],
    )

    base_channel._agent.ask.assert_called_once()
    base_channel._agent.resume_after_confirmation.assert_not_called()


@pytest.mark.asyncio
async def test_start_conversation_calls_resume_when_pending_interrupt(base_channel):
    """When a pending interrupt exists, start_conversation should call
    resume_after_confirmation(REJECT) with new_messages."""
    session_id = uuid.uuid4()
    await base_channel._sessions_storage.create_session(session_id)

    new_msg = AgentMessage(role="user", text="new msg")
    base_channel._agent.has_pending_interrupt = AsyncMock(return_value=True)
    base_channel._agent.ask = MagicMock(return_value=_async_gen([]))
    base_channel._agent.resume_after_confirmation = MagicMock(return_value=_async_gen([]))

    await base_channel.start_conversation(
        session_id=session_id,
        channel_internal_id=1,
        new_messages=[new_msg],
    )

    base_channel._agent.ask.assert_not_called()
    base_channel._agent.resume_after_confirmation.assert_called_once()
    call_kwargs = base_channel._agent.resume_after_confirmation.call_args.kwargs
    assert call_kwargs["session_id"] == session_id
    assert call_kwargs["decision"] == DecisionEnum.REJECT
    assert call_kwargs["new_messages"] == [new_msg]
