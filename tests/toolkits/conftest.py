import uuid

import pytest
import pytest_asyncio

from microclaw.agents.settings import MCPRemoteSettings
from microclaw.dto import UserRoleEnum
from microclaw.toolkits.accessors import AllUsersAccessor, CurrentUserAccessor
from microclaw.toolkits.context import TOOLKIT_CONTEXT, ToolkitExecutionContext
from microclaw.toolkits.dto import DiscoveryInfo
from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum
from microclaw.toolkits.mcp_manager.toolkit import MCPManagerToolKit
from microclaw.toolkits.skills_manager.toolkit import SkillsManagerToolKit
from microclaw.users_storages.dto import UserCreate


@pytest_asyncio.fixture
async def toolkit_context(users_storage, sessions_storage):
    user = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.USER))
    accessor = CurrentUserAccessor(
        user_id=user.id,
        storage=users_storage,
        writable=True,
        invalidate_cache=lambda: None,
    )
    context = ToolkitExecutionContext(
        session_id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        channel_key="test",
        channel_internal_id="123",
        current_user_accessor=accessor,
        all_users_accessor=AllUsersAccessor(
            storage=users_storage, writable=True
        ),
    )
    token = TOOLKIT_CONTEXT.set(context)
    try:
        yield context
    finally:
        TOOLKIT_CONTEXT.reset(token)


@pytest_asyncio.fixture
async def skills_context(users_storage):
    user = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.USER))
    accessor = CurrentUserAccessor(
        user_id=user.id,
        storage=users_storage,
        writable=True,
        invalidate_cache=lambda: None,
    )
    context = ToolkitExecutionContext(
        session_id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        channel_key="test",
        channel_internal_id="123",
        current_user_accessor=accessor,
        all_skills={
            "global_skill": DiscoveryInfo(name="global_skill", description="desc")
        },
    )
    token = TOOLKIT_CONTEXT.set(context)
    try:
        yield context
    finally:
        TOOLKIT_CONTEXT.reset(token)


@pytest_asyncio.fixture
async def skills_admin_context(users_storage):
    admin = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.ADMIN))
    target = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.USER))
    accessor = CurrentUserAccessor(
        user_id=admin.id,
        storage=users_storage,
        writable=True,
        invalidate_cache=lambda: None,
    )
    all_users_accessor = AllUsersAccessor(storage=users_storage, writable=True)
    context = ToolkitExecutionContext(
        session_id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        channel_key="test",
        channel_internal_id="456",
        current_user_accessor=accessor,
        all_users_accessor=all_users_accessor,
        all_skills={
            "global_skill": DiscoveryInfo(name="global_skill", description="desc")
        },
    )
    token = TOOLKIT_CONTEXT.set(context)
    try:
        yield context, target, admin
    finally:
        TOOLKIT_CONTEXT.reset(token)


@pytest_asyncio.fixture
async def mcp_context(users_storage):
    user = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.USER))
    accessor = CurrentUserAccessor(
        user_id=user.id,
        storage=users_storage,
        writable=True,
        invalidate_cache=lambda: None,
    )
    context = ToolkitExecutionContext(
        session_id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        channel_key="test",
        channel_internal_id="123",
        current_user_accessor=accessor,
        all_mcp={
            "global_mcp": MCPRemoteSettings(name="global_mcp", url="http://example.com")
        },
    )
    token = TOOLKIT_CONTEXT.set(context)
    try:
        yield context
    finally:
        TOOLKIT_CONTEXT.reset(token)


@pytest_asyncio.fixture
async def mcp_admin_context(users_storage):
    admin = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.ADMIN))
    target = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.USER))
    accessor = CurrentUserAccessor(
        user_id=admin.id,
        storage=users_storage,
        writable=True,
        invalidate_cache=lambda: None,
    )
    all_users_accessor = AllUsersAccessor(storage=users_storage, writable=True)
    context = ToolkitExecutionContext(
        session_id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        channel_key="test",
        channel_internal_id="456",
        current_user_accessor=accessor,
        all_users_accessor=all_users_accessor,
        all_mcp={
            "global_mcp": MCPRemoteSettings(name="global_mcp", url="http://example.com")
        },
    )
    token = TOOLKIT_CONTEXT.set(context)
    try:
        yield context, target, admin
    finally:
        TOOLKIT_CONTEXT.reset(token)


@pytest.fixture
def make_skills_manager_toolkit(tmp_path):
    def _make(
        install_mode=PermissionModeEnum.REQUEST,
        remove_mode=PermissionModeEnum.REQUEST,
        update_mode=PermissionModeEnum.REQUEST,
        enable_mode=PermissionModeEnum.REQUEST,
        source_mode=SourceModeEnum.ALL,
        skills_mp_client=None,
        discover_func=None,
        skills_directory=None,
    ):
        from microclaw.toolkits import ToolKitSettings

        settings = ToolKitSettings(
            path="microclaw.toolkits.skills_manager.toolkit.SkillsManagerToolKit",
            args={
                "install_mode": install_mode.value
                if isinstance(install_mode, PermissionModeEnum)
                else install_mode,
                "remove_mode": remove_mode.value
                if isinstance(remove_mode, PermissionModeEnum)
                else remove_mode,
                "update_mode": update_mode.value
                if isinstance(update_mode, PermissionModeEnum)
                else update_mode,
                "enable_mode": enable_mode.value
                if isinstance(enable_mode, PermissionModeEnum)
                else enable_mode,
                "source_mode": source_mode.value
                if isinstance(source_mode, SourceModeEnum)
                else source_mode,
                "skills_directory": str(skills_directory or tmp_path),
            },
        )
        return SkillsManagerToolKit(
            key="skills_manager",
            settings=settings,
        )

    return _make


@pytest.fixture
def make_mcp_manager_toolkit():
    def _make(
        add_mode=PermissionModeEnum.REQUEST,
        remove_mode=PermissionModeEnum.REQUEST,
        source_mode=SourceModeEnum.ALL,
        mcp_client_factory=None,
    ):
        from microclaw.toolkits import ToolKitSettings

        settings = ToolKitSettings(
            path="microclaw.toolkits.mcp_manager.toolkit.MCPManagerToolKit",
            args={
                "add_mode": add_mode.value
                if isinstance(add_mode, PermissionModeEnum)
                else add_mode,
                "remove_mode": remove_mode.value
                if isinstance(remove_mode, PermissionModeEnum)
                else remove_mode,
                "source_mode": source_mode.value
                if isinstance(source_mode, SourceModeEnum)
                else source_mode,
            },
        )
        return MCPManagerToolKit(
            key="mcp_manager",
            settings=settings,
        )

    return _make
