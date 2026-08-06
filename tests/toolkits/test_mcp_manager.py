import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from microclaw.agents.settings import AgentSettings, MCPRemoteSettings, MCPLocalSettings
from microclaw.dto import DecisionEnum, UserRoleEnum
from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.accessors import CurrentUserAccessor, AllUsersAccessor
from microclaw.toolkits.context import TOOLKIT_CONTEXT, ToolkitExecutionContext
from microclaw.toolkits.dto import DiscoveryInfo
from microclaw.toolkits.mcp_manager import MCPManagerToolKit
from microclaw.users_storages.memory.storage import MemoryUsersStorage
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings


@pytest.fixture
def mcp_manager_toolkit():
    settings = ToolKitSettings(
        path="microclaw.toolkits.mcp_manager.MCPManagerToolKit",
        args={},
    )
    return MCPManagerToolKit(key="mcp_manager", settings=settings)


@pytest.fixture
def users_storage():
    return MemoryUsersStorage(settings=MemoryUsersStorageSettings())


@pytest_asyncio.fixture
async def toolkit_context(users_storage):
    user = await users_storage.create_user(role=UserRoleEnum.USER)
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
            "global_mcp": DiscoveryInfo(name="global_mcp", description="global desc"),
        },
    )
    token = TOOLKIT_CONTEXT.set(context)
    yield context
    TOOLKIT_CONTEXT.reset(token)


@pytest_asyncio.fixture
async def admin_context(users_storage):
    user = await users_storage.create_user(role=UserRoleEnum.USER)
    admin = await users_storage.create_user(role=UserRoleEnum.ADMIN)
    accessor = CurrentUserAccessor(
        user_id=admin.id,
        storage=users_storage,
        writable=True,
        invalidate_cache=lambda: None,
    )
    all_accessor = AllUsersAccessor(storage=users_storage, writable=True)
    context = ToolkitExecutionContext(
        session_id=uuid.uuid4(),
        request_id=uuid.uuid4(),
        channel_key="test",
        channel_internal_id="456",
        current_user_accessor=accessor,
        all_users_accessor=all_accessor,
        all_mcp={
            "global_mcp": DiscoveryInfo(name="global_mcp", description="global desc"),
        },
    )
    token = TOOLKIT_CONTEXT.set(context)
    yield context, user, admin
    TOOLKIT_CONTEXT.reset(token)


# ─── basic ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_global_mcp(mcp_manager_toolkit, toolkit_context):
    result = await mcp_manager_toolkit.list_global_mcp()
    assert len(result) == 1
    assert result[0]["name"] == "global_mcp"


@pytest.mark.asyncio
async def test_list_my_mcp__empty(mcp_manager_toolkit, toolkit_context):
    result = await mcp_manager_toolkit.list_my_mcp()
    assert result == []


@pytest.mark.asyncio
async def test_add_custom_mcp__remote(mcp_manager_toolkit, toolkit_context, users_storage):
    from microclaw.toolkits.enums import PermissionModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW

    config = MCPRemoteSettings(name="my_remote", url="http://example.com/mcp")
    result = await mcp_manager_toolkit.add_custom_mcp(config)
    assert "added" in result.lower()

    user = await users_storage.get_user(toolkit_context.current_user_accessor.user_id)
    agent = AgentSettings.model_validate(user.agent)
    assert any(
        isinstance(m, MCPRemoteSettings) and m.name == "my_remote" for m in agent.mcp
    )


@pytest.mark.asyncio
async def test_add_custom_mcp__local(mcp_manager_toolkit, toolkit_context, users_storage):
    from microclaw.toolkits.enums import PermissionModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW

    config = MCPLocalSettings(name="my_local", command="npx", args=["-y", "@test"])
    result = await mcp_manager_toolkit.add_custom_mcp(config)
    assert "added" in result.lower()

    user = await users_storage.get_user(toolkit_context.current_user_accessor.user_id)
    agent = AgentSettings.model_validate(user.agent)
    assert any(
        isinstance(m, MCPLocalSettings) and m.name == "my_local" for m in agent.mcp
    )


@pytest.mark.asyncio
async def test_enable_mcp(mcp_manager_toolkit, toolkit_context, users_storage):
    from microclaw.toolkits.enums import PermissionModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW

    result = await mcp_manager_toolkit.enable_mcp("global_mcp")
    assert "enabled" in result.lower()

    user = await users_storage.get_user(toolkit_context.current_user_accessor.user_id)
    agent = AgentSettings.model_validate(user.agent)
    assert any(m == "global_mcp" for m in agent.mcp)


@pytest.mark.asyncio
async def test_enable_mcp__not_found(mcp_manager_toolkit, toolkit_context):
    from microclaw.toolkits.enums import PermissionModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW
    with pytest.raises(ValueError, match="not found"):
        await mcp_manager_toolkit.enable_mcp("nonexistent")


@pytest.mark.asyncio
async def test_enable_mcp__already_exists(mcp_manager_toolkit, toolkit_context, users_storage):
    from microclaw.toolkits.enums import PermissionModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW

    user_id = toolkit_context.current_user_accessor.user_id
    await users_storage.update_user(user_id=user_id, agent_settings=AgentSettings(mcp=["global_mcp"]))
    with pytest.raises(ValueError, match="already exists"):
        await mcp_manager_toolkit.enable_mcp("global_mcp")


@pytest.mark.asyncio
async def test_remove_mcp(mcp_manager_toolkit, toolkit_context, users_storage):
    user_id = toolkit_context.current_user_accessor.user_id
    await users_storage.update_user(
        user_id=user_id,
        agent_settings=AgentSettings(mcp=[MCPRemoteSettings(name="to_remove", url="http://example.com")]),
    )
    import microclaw.toolkits.mcp_manager.toolkit as mcp_module
    orig = mcp_module.interrupt
    mcp_module.interrupt = lambda *a, **kw: DecisionEnum.APPROVE.value
    try:
        await mcp_manager_toolkit.remove_mcp("to_remove")
        user = await users_storage.get_user(user_id)
        agent = AgentSettings.model_validate(user.agent)
        assert not agent.mcp or all(
            (m.name if hasattr(m, "name") else m) != "to_remove" for m in agent.mcp
        )
    finally:
        mcp_module.interrupt = orig


@pytest.mark.asyncio
async def test_test_mcp__success(mcp_manager_toolkit, toolkit_context, users_storage):
    user_id = toolkit_context.current_user_accessor.user_id
    await users_storage.update_user(
        user_id=user_id,
        agent_settings=AgentSettings(mcp=[MCPRemoteSettings(name="test_mcp", url="http://example.com")]),
    )
    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[MagicMock(), MagicMock()])
    with patch("microclaw.toolkits.mcp_manager.toolkit.MultiServerMCPClient", return_value=mock_client):
        result = await mcp_manager_toolkit.test_mcp("test_mcp")
    assert "connected successfully" in result.lower()


# ─── source_mode checks ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_custom_mcp__global_denied(mcp_manager_toolkit, toolkit_context):
    from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW
    mcp_manager_toolkit._settings.source_mode = SourceModeEnum.GLOBAL
    config = MCPRemoteSettings(name="any", url="http://example.com")
    with pytest.raises(PermissionError):
        await mcp_manager_toolkit.add_custom_mcp(config)


@pytest.mark.asyncio
async def test_add_custom_mcp__empty_denied(mcp_manager_toolkit, toolkit_context):
    from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW
    mcp_manager_toolkit._settings.source_mode = SourceModeEnum.EMPTY
    config = MCPRemoteSettings(name="any", url="http://example.com")
    with pytest.raises(PermissionError):
        await mcp_manager_toolkit.add_custom_mcp(config)


@pytest.mark.asyncio
async def test_enable_mcp__marketplace_denied(mcp_manager_toolkit, toolkit_context):
    from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW
    mcp_manager_toolkit._settings.source_mode = SourceModeEnum.MARKETPLACE
    with pytest.raises(PermissionError):
        await mcp_manager_toolkit.enable_mcp("global_mcp")


@pytest.mark.asyncio
async def test_enable_mcp__empty_denied(mcp_manager_toolkit, toolkit_context):
    from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW
    mcp_manager_toolkit._settings.source_mode = SourceModeEnum.EMPTY
    with pytest.raises(PermissionError):
        await mcp_manager_toolkit.enable_mcp("global_mcp")


# ─── cross-user ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enable_mcp__cross_user(admin_context, users_storage, mcp_manager_toolkit):
    from microclaw.toolkits.enums import PermissionModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW
    context, target_user, admin_user = admin_context

    result = await mcp_manager_toolkit.enable_mcp("global_mcp", user_id=str(target_user.id))
    assert "enabled" in result.lower()

    target = await users_storage.get_user(target_user.id)
    agent = AgentSettings.model_validate(target.agent)
    assert any(m == "global_mcp" for m in agent.mcp)


@pytest.mark.asyncio
async def test_list_my_mcp__cross_user(admin_context, mcp_manager_toolkit):
    from microclaw.toolkits.enums import PermissionModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW
    context, target_user, admin_user = admin_context

    await mcp_manager_toolkit.enable_mcp("global_mcp", user_id=str(target_user.id))
    result = await mcp_manager_toolkit.list_my_mcp(user_id=str(target_user.id))
    assert len(result) == 1
    assert result[0]["name"] == "global_mcp"


@pytest.mark.asyncio
async def test_cross_user__no_accessor_denied(mcp_manager_toolkit, toolkit_context, users_storage):
    from microclaw.toolkits.enums import PermissionModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW
    other = await users_storage.create_user(role=UserRoleEnum.USER)
    with pytest.raises(PermissionError, match="Cross-user access not granted"):
        await mcp_manager_toolkit.enable_mcp("global_mcp", user_id=str(other.id))


@pytest.mark.asyncio
async def test_cross_user__read_only_denied(admin_context, mcp_manager_toolkit):
    from microclaw.toolkits.enums import PermissionModeEnum
    mcp_manager_toolkit._settings.add_mode = PermissionModeEnum.ALLOW
    context, target_user, admin_user = admin_context

    # Make all_users_accessor read-only for this test
    context_readonly = ToolkitExecutionContext(
        session_id=context.session_id,
        request_id=context.request_id,
        channel_key=context.channel_key,
        channel_internal_id=context.channel_internal_id,
        current_user_accessor=context.current_user_accessor,
        all_users_accessor=AllUsersAccessor(
            storage=context.current_user_accessor._storage, writable=False
        ),
        all_mcp=context.all_mcp,
    )
    token = TOOLKIT_CONTEXT.set(context_readonly)
    try:
        with pytest.raises(PermissionError, match="Cross-user write access not granted"):
            await mcp_manager_toolkit.enable_mcp("global_mcp", user_id=str(target_user.id))
    finally:
        TOOLKIT_CONTEXT.reset(token)
