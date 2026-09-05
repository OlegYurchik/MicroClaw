import uuid

import pytest

from microclaw.sessions_storages.dto import SessionCreate
from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.accessors import CurrentUserAccessor
from microclaw.toolkits.context import TOOLKIT_CONTEXT, ToolkitExecutionContext
from microclaw.toolkits.users.toolkit import UsersToolKit
from microclaw.users_storages.dto import UserChannelCreate, UserCreate


@pytest.fixture
def users_toolkit() -> UsersToolKit:
    settings = ToolKitSettings(
        path="microclaw.toolkits.users.toolkit.UsersToolKit",
        args={},
    )
    return UsersToolKit(key="users", settings=settings)


class TestGetMyProfile:
    @pytest.mark.asyncio
    async def test_get_my_profile_success(self, users_toolkit, toolkit_context):
        result = await users_toolkit.get_my_profile()
        assert result is not None
        user = await toolkit_context.current_user_accessor.get()
        assert result["id"] == str(user.id)

    @pytest.mark.asyncio
    async def test_get_my_profile_no_context(self, users_toolkit):
        token = TOOLKIT_CONTEXT.set(None)
        try:
            with pytest.raises(
                RuntimeError, match="Not available outside channel context."
            ):
                await users_toolkit.get_my_profile()
        finally:
            TOOLKIT_CONTEXT.reset(token)

    @pytest.mark.asyncio
    async def test_get_my_profile_no_user(self, users_toolkit, users_storage):
        accessor = CurrentUserAccessor(
            user_id=uuid.uuid4(),
            storage=users_storage,
            writable=True,
            invalidate_cache=lambda: None,
        )
        ctx = ToolkitExecutionContext(
            session_id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            channel_key="test",
            channel_internal_id="123",
            current_user_accessor=accessor,
        )
        token = TOOLKIT_CONTEXT.set(ctx)
        try:
            result = await users_toolkit.get_my_profile()
            assert result is None
        finally:
            TOOLKIT_CONTEXT.reset(token)


class TestListUsers:
    @pytest.mark.asyncio
    async def test_list_users_requires_all_users(self, users_toolkit, users_storage):
        user = await users_storage.create_user(data=UserCreate())
        accessor = CurrentUserAccessor(
            user_id=user.id,
            storage=users_storage,
            writable=True,
            invalidate_cache=lambda: None,
        )
        ctx = ToolkitExecutionContext(
            session_id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            channel_key="test",
            channel_internal_id="123",
            current_user_accessor=accessor,
        )
        token = TOOLKIT_CONTEXT.set(ctx)
        try:
            result = await users_toolkit.list_users()
            assert result == []
        finally:
            TOOLKIT_CONTEXT.reset(token)

    @pytest.mark.asyncio
    async def test_list_users_with_limit(
        self, users_toolkit, toolkit_context, users_storage
    ):
        await users_storage.create_user(data=UserCreate())
        await users_storage.create_user(data=UserCreate())
        result = await users_toolkit.list_users(limit=2)
        assert len(result) == 2


class TestGetUser:
    @pytest.mark.asyncio
    async def test_get_user_own_profile(self, users_toolkit, users_storage):
        user = await users_storage.create_user(data=UserCreate())
        accessor = CurrentUserAccessor(
            user_id=user.id,
            storage=users_storage,
            writable=True,
            invalidate_cache=lambda: None,
        )
        ctx = ToolkitExecutionContext(
            session_id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            channel_key="test",
            channel_internal_id="123",
            current_user_accessor=accessor,
        )
        token = TOOLKIT_CONTEXT.set(ctx)
        try:
            result = await users_toolkit.get_user(str(user.id))
            assert result is not None
            assert result["id"] == str(user.id)
        finally:
            TOOLKIT_CONTEXT.reset(token)

    @pytest.mark.asyncio
    async def test_get_user_other_with_all_users(
        self, users_toolkit, toolkit_context, users_storage
    ):
        other = await users_storage.create_user(data=UserCreate())
        result = await users_toolkit.get_user(str(other.id))
        assert result is not None
        assert result["id"] == str(other.id)

    @pytest.mark.asyncio
    async def test_get_user_other_denied(self, users_toolkit, users_storage):
        me = await users_storage.create_user(data=UserCreate())
        other = await users_storage.create_user(data=UserCreate())
        accessor = CurrentUserAccessor(
            user_id=me.id,
            storage=users_storage,
            writable=True,
            invalidate_cache=lambda: None,
        )
        ctx = ToolkitExecutionContext(
            session_id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            channel_key="test",
            channel_internal_id="123",
            current_user_accessor=accessor,
        )
        token = TOOLKIT_CONTEXT.set(ctx)
        try:
            result = await users_toolkit.get_user(str(other.id))
            assert result is None
        finally:
            TOOLKIT_CONTEXT.reset(token)


class TestGetUserBySession:
    @pytest.mark.asyncio
    async def test_get_user_by_session_success(
        self, users_toolkit, toolkit_context, sessions_storage, users_storage
    ):
        user = await toolkit_context.current_user_accessor.get()
        session = await sessions_storage.create_session(
            data=SessionCreate(channel_key="test", channel_internal_id="123")
        )
        await users_storage.create_user_channel(
            data=UserChannelCreate(
                user_id=user.id,
                channel_key="test",
                channel_internal_id="123",
                actual_session_id=session.id,
            )
        )
        result = await users_toolkit.get_user_by_session(str(session.id))
        assert result is not None
        assert result["id"] == str(user.id)

    @pytest.mark.asyncio
    async def test_get_user_by_session_not_found(self, users_toolkit, toolkit_context):
        result = await users_toolkit.get_user_by_session(str(uuid.uuid4()))
        assert result is None
