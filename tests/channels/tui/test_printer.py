import json
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from microclaw.agents import Agent
from microclaw.channels.tui.printer import AgentMessagePrinter
from microclaw.channels.tui.ui import RoleEnum
from microclaw.dto import AgentMessage, AgentMessageRoleEnum, Session, Spending
from microclaw.sessions_storages import SessionsStorageInterface


@pytest.fixture
def mock_app() -> MagicMock:
    app = MagicMock()
    app.add_message = AsyncMock()
    app.update_message = MagicMock()
    app.add_confirmation_message = AsyncMock()
    app.show_thinking = MagicMock()
    app.hide_thinking = MagicMock()
    app.update_stats = MagicMock()
    return app


@pytest.fixture
def mock_sessions_storage() -> MagicMock:
    storage = MagicMock(spec=SessionsStorageInterface)
    storage.get_session = AsyncMock()
    return storage


@pytest.fixture
def mock_agent() -> MagicMock:
    agent = MagicMock(spec=Agent)
    agent.get_model_context_window_size = MagicMock(return_value=8000)
    return agent


@pytest.fixture
def printer(mock_app, mock_sessions_storage, mock_agent) -> AgentMessagePrinter:
    return AgentMessagePrinter(
        app=mock_app,
        session_id=uuid.uuid4(),
        sessions_storage=mock_sessions_storage,
        agent=mock_agent,
        debug=False,
    )


class TestAgentMessagePrinter:
    @pytest.mark.asyncio
    async def test_aenter_shows_thinking(self, printer, mock_app):
        async with printer:
            mock_app.show_thinking.assert_called()

    @pytest.mark.asyncio
    async def test_aexit_hides_thinking(self, printer, mock_app):
        async with printer:
            pass
        mock_app.hide_thinking.assert_called()

    @pytest.mark.asyncio
    async def test_aexit_on_exception_shows_error(self, printer, mock_app):
        async with printer:
            raise ValueError("boom")
        mock_app.add_message.assert_awaited()
        call_args = mock_app.add_message.await_args
        assert call_args.kwargs["role"] == RoleEnum.SYSTEM
        assert "Internal error" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_aexit_on_exception_debug_shows_trace(self, printer, mock_app):
        printer._debug = True
        async with printer:
            raise ValueError("boom")
        call_args = mock_app.add_message.await_args
        assert "Got exception" in call_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_handle_new_message_assistant_text(self, printer, mock_app):
        message = AgentMessage(role=AgentMessageRoleEnum.ASSISTANT, text="hello")
        await printer.handle_new_message(message)
        mock_app.add_message.assert_awaited_with(role=RoleEnum.AI, text="hello")

    @pytest.mark.asyncio
    async def test_handle_new_message_assistant_chunks(self, printer, mock_app):
        message1 = AgentMessage(
            role=AgentMessageRoleEnum.ASSISTANT, text="hello", chunked_message_id="1"
        )
        message2 = AgentMessage(
            role=AgentMessageRoleEnum.ASSISTANT, text=" world", chunked_message_id="1"
        )
        await printer.register_new_message(message1)
        await printer.register_new_message(message2)
        assert mock_app.add_message.await_count == 1
        assert mock_app.update_message.call_count == 1
        mock_app.update_message.assert_called_with(role=RoleEnum.AI, text="hello world")

    @pytest.mark.asyncio
    async def test_handle_new_message_request_confirmation(self, printer, mock_app):
        entries = json.dumps([{"description": "confirm this"}])
        message = AgentMessage(
            role=AgentMessageRoleEnum.REQUEST_CONFIRMATION, text=entries
        )
        await printer.handle_new_message(message)
        mock_app.add_confirmation_message.assert_awaited_with(
            question="confirm this", session_id=printer._session_id
        )

    @pytest.mark.asyncio
    async def test_handle_new_message_non_assistant_ignored(self, printer, mock_app):
        message = AgentMessage(role=AgentMessageRoleEnum.USER, text="hello")
        await printer.handle_new_message(message)
        mock_app.add_message.assert_not_awaited()



    @pytest.mark.asyncio
    async def test_print_spent_with_context(
        self, printer, mock_sessions_storage, mock_app, mock_agent
    ):
        session_id = printer._session_id
        mock_sessions_storage.get_session = AsyncMock(
            return_value=Session(
                id=session_id,
                channel_key="tui",
                channel_internal_id="1",
                context_size=4000,
                spending=Spending(cost=0.42, currency="RUB"),
            )
        )
        await printer.print_spent()
        mock_app.update_stats.assert_called()
        call_kwargs = mock_app.update_stats.call_args.kwargs
        assert call_kwargs["context_usage"] == 50.0
        assert call_kwargs["cost"] == 0.42
        assert call_kwargs["currency"] == "RUB"

    @pytest.mark.asyncio
    async def test_print_spent_no_session(
        self, printer, mock_sessions_storage, mock_app
    ):
        mock_sessions_storage.get_session = AsyncMock(return_value=None)
        await printer.print_spent()
        mock_app.update_stats.assert_called()
        call_kwargs = mock_app.update_stats.call_args.kwargs
        assert call_kwargs["context_usage"] == 0.0
        assert call_kwargs["cost"] == 0.0
        assert call_kwargs["currency"] == "$"

    @pytest.mark.asyncio
    async def test_print_spent_no_model_size(self, printer, mock_agent, mock_app):
        mock_agent.get_model_context_window_size = MagicMock(return_value=None)
        await printer.print_spent()
        call_kwargs = mock_app.update_stats.call_args.kwargs
        assert call_kwargs["context_usage"] == 0.0
