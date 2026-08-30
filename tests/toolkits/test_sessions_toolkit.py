import uuid

import pytest
import pytest_asyncio

from microclaw.dto import AgentMessage, AgentMessageRoleEnum
from microclaw.sessions_storages.dto import MessageCreate, SessionCreate
from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.accessors import AllSessionsAccessor
from microclaw.toolkits.context import TOOLKIT_CONTEXT, ToolkitExecutionContext
from microclaw.toolkits.sessions.toolkit import SessionsToolKit
from microclaw.users_storages.dto import UserChannelCreate


@pytest_asyncio.fixture
async def sessions_toolkit_context(toolkit_context, sessions_storage):

    ctx = toolkit_context
    new_ctx = ToolkitExecutionContext(
        session_id=ctx.session_id,
        request_id=ctx.request_id,
        channel_key=ctx.channel_key,
        channel_internal_id=ctx.channel_internal_id,
        current_user_accessor=ctx.current_user_accessor,
        all_users_accessor=ctx.all_users_accessor,
        sessions_accessor=AllSessionsAccessor(storage=sessions_storage),
    )
    token = TOOLKIT_CONTEXT.set(new_ctx)
    try:
        yield new_ctx
    finally:
        TOOLKIT_CONTEXT.reset(token)


@pytest_asyncio.fixture
async def sessions_toolkit(sessions_toolkit_context):
    settings = ToolKitSettings(
        path="microclaw.toolkits.sessions.toolkit.SessionsToolKit",
        args={"max_results": 10},
    )
    return SessionsToolKit(key="sessions", settings=settings)


class TestSearchSessions:
    @pytest.mark.asyncio
    async def test_returns_empty_without_context(self, sessions_toolkit):
        result = await sessions_toolkit.search_sessions("query")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_current_user(
        self,
        sessions_toolkit,
        sessions_storage,
        users_storage,
        sessions_toolkit_context,
    ):
        user = await sessions_toolkit_context.current_user_accessor.get()
        session_id = uuid.uuid4()
        await sessions_storage.create_session(
            data=SessionCreate(
                id=session_id, channel_key="test", channel_internal_id="test"
            )
        )
        await users_storage.create_user_channel(
            data=UserChannelCreate(
                user_id=user.id, channel_key="test", channel_internal_id="test"
            )
        )
        await sessions_storage.create_message(
            data=MessageCreate(
                session_id=session_id,
                message=AgentMessage(
                    role=AgentMessageRoleEnum.USER, text="hello world query"
                ),
            )
        )

        result = await sessions_toolkit.search_sessions("query")
        assert len(result) == 1
        assert "hello world query" in result[0]

    @pytest.mark.asyncio
    async def test_limit_respected(
        self,
        sessions_toolkit,
        sessions_storage,
        users_storage,
        sessions_toolkit_context,
    ):
        user = await sessions_toolkit_context.current_user_accessor.get()
        for i in range(3):
            session_id = uuid.uuid4()
            await sessions_storage.create_session(
                data=SessionCreate(
                    id=session_id, channel_key="test", channel_internal_id=f"test{i}"
                )
            )
            await users_storage.create_user_channel(
                data=UserChannelCreate(
                    user_id=user.id, channel_key="test", channel_internal_id=f"test{i}"
                )
            )
            await sessions_storage.create_message(
                data=MessageCreate(
                    session_id=session_id,
                    message=AgentMessage(
                        role=AgentMessageRoleEnum.USER, text=f"query {i}"
                    ),
                )
            )

        result = await sessions_toolkit.search_sessions("query", limit=2)
        assert len(result) == 2


class TestGetSession:
    @pytest.mark.asyncio
    async def test_success(
        self,
        sessions_toolkit,
        sessions_storage,
        users_storage,
        sessions_toolkit_context,
    ):
        user = await sessions_toolkit_context.current_user_accessor.get()
        session_id = uuid.uuid4()
        await sessions_storage.create_session(
            data=SessionCreate(
                id=session_id, channel_key="test", channel_internal_id="test"
            )
        )
        await users_storage.create_user_channel(
            data=UserChannelCreate(
                user_id=user.id, channel_key="test", channel_internal_id="test"
            )
        )
        await sessions_storage.create_message(
            data=MessageCreate(
                session_id=session_id,
                message=AgentMessage(role=AgentMessageRoleEnum.USER, text="hello"),
            )
        )

        result = await sessions_toolkit.get_session(session_id)
        assert result is not None
        assert result.session_id == session_id
        assert result.message_count == 1

    @pytest.mark.asyncio
    async def test_not_found(self, sessions_toolkit):
        result = await sessions_toolkit.get_session(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_no_messages_returns_none(
        self,
        sessions_toolkit,
        sessions_storage,
        users_storage,
        sessions_toolkit_context,
    ):
        user = await sessions_toolkit_context.current_user_accessor.get()
        session_id = uuid.uuid4()
        await sessions_storage.create_session(
            data=SessionCreate(
                id=session_id, channel_key="test", channel_internal_id="test"
            )
        )
        await users_storage.create_user_channel(
            data=UserChannelCreate(
                user_id=user.id, channel_key="test", channel_internal_id="test"
            )
        )

        result = await sessions_toolkit.get_session(session_id)
        assert result is None


class TestListSessions:
    @pytest.mark.asyncio
    async def test_list_current_user(
        self,
        sessions_toolkit,
        sessions_storage,
        users_storage,
        sessions_toolkit_context,
    ):
        user = await sessions_toolkit_context.current_user_accessor.get()
        session_id = uuid.uuid4()
        await sessions_storage.create_session(
            data=SessionCreate(
                id=session_id, channel_key="test", channel_internal_id="test"
            )
        )
        await users_storage.create_user_channel(
            data=UserChannelCreate(
                user_id=user.id, channel_key="test", channel_internal_id="test"
            )
        )
        await sessions_storage.create_message(
            data=MessageCreate(
                session_id=session_id,
                message=AgentMessage(role=AgentMessageRoleEnum.USER, text="hello"),
            )
        )

        result = await sessions_toolkit.list_sessions()
        assert len(result) == 1
        assert result[0].session_id == session_id

    @pytest.mark.asyncio
    async def test_limit_respected(
        self,
        sessions_toolkit,
        sessions_storage,
        users_storage,
        sessions_toolkit_context,
    ):
        user = await sessions_toolkit_context.current_user_accessor.get()
        for i in range(3):
            session_id = uuid.uuid4()
            await sessions_storage.create_session(
                data=SessionCreate(
                    id=session_id, channel_key="test", channel_internal_id=f"test{i}"
                )
            )
            await users_storage.create_user_channel(
                data=UserChannelCreate(
                    user_id=user.id, channel_key="test", channel_internal_id=f"test{i}"
                )
            )
            await sessions_storage.create_message(
                data=MessageCreate(
                    session_id=session_id,
                    message=AgentMessage(
                        role=AgentMessageRoleEnum.USER, text=f"msg {i}"
                    ),
                )
            )

        result = await sessions_toolkit.list_sessions(limit=2)
        assert len(result) == 2
