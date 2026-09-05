from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
import pytest_asyncio
import skilly

from microclaw.agents.settings import AgentSettings
from microclaw.dto import DecisionEnum, UserRoleEnum
from microclaw.toolkits import ToolKitSettings
from microclaw.toolkits.accessors import AllUsersAccessor, CurrentUserAccessor
from microclaw.toolkits.context import TOOLKIT_CONTEXT, ToolkitExecutionContext
from microclaw.toolkits.dto import DiscoveryInfo
from microclaw.toolkits.skills_manager import SkillsManagerToolKit
from microclaw.users_storages.dto import UserCreate, UserUpdate
from microclaw.users_storages.filters import UserFilter
from microclaw.users_storages.memory.settings import MemoryUsersStorageSettings
from microclaw.users_storages.memory.storage import MemoryUsersStorage


@pytest.fixture
def skills_manager_toolkit(tmp_path):
    settings = ToolKitSettings(
        path="microclaw.toolkits.skills_manager.SkillsManagerToolKit",
        args={"skills_directory": str(tmp_path)},
    )
    return SkillsManagerToolKit(key="skills_manager", settings=settings)


@pytest.fixture
def users_storage():
    return MemoryUsersStorage(settings=MemoryUsersStorageSettings())


@pytest_asyncio.fixture
async def toolkit_context(users_storage):
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
    )
    token = TOOLKIT_CONTEXT.set(context)
    yield context
    TOOLKIT_CONTEXT.reset(token)


@pytest_asyncio.fixture
async def admin_context(users_storage):
    admin = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.ADMIN))
    target = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.USER))
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
        all_skills={
            "global_skill": DiscoveryInfo(name="global_skill", description="desc"),
        },
    )
    token = TOOLKIT_CONTEXT.set(context)
    yield context, target, admin
    TOOLKIT_CONTEXT.reset(token)


# ─── basic ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_installed_skills__empty(skills_manager_toolkit, toolkit_context):
    result = await skills_manager_toolkit.list_installed_skills()
    assert result == []


@pytest.mark.asyncio
async def test_search_skills(skills_manager_toolkit, toolkit_context, monkeypatch):
    from skilly.skillsmp.client import (
        SkillsMpFilters,
        SkillsMpPagination,
        SkillsMpSearchData,
        SkillsMpSearchResult,
        SkillsMpSkill,
    )
    def mock_search(self, query):
        return SkillsMpSearchResult(
            success=True,
            data=SkillsMpSearchData(
                skills=[SkillsMpSkill(
                    id="1", name="test-skill", author="tester",
                    description="a test skill",
                    github_url="https://github.com/user/test-skill",
                    skill_url="https://example.com/test-skill",
                )],
                pagination=SkillsMpPagination(
                    page=1, limit=20, total=1, total_pages=1,
                    has_next=False, has_prev=False, total_is_exact=True,
                ),
                filters=SkillsMpFilters(search=query, sort_by="stars"),
            ),
        )
    monkeypatch.setattr(
        "microclaw.toolkits.skills_manager.toolkit.SkillsMp.search", mock_search
    )
    result = await skills_manager_toolkit.search_skills("test")
    assert len(result) == 1
    assert result[0]["name"] == "test-skill"


@pytest.mark.asyncio
async def test_install_skill__success(skills_manager_toolkit, toolkit_context, monkeypatch):
    from microclaw.toolkits.enums import PermissionModeEnum
    skills_manager_toolkit.arguments.install_mode = PermissionModeEnum.ALLOW

    def mock_mp_search(self, query):
        skill_mock = MagicMock()
        skill_mock.name = "new-skill"
        skill_mock.github_url = "https://github.com/user/new-skill"
        return MagicMock(data=MagicMock(skills=[skill_mock]))
    monkeypatch.setattr(
        "microclaw.toolkits.skills_manager.toolkit.SkillsMp.search", mock_mp_search
    )
    monkeypatch.setattr(
        "microclaw.toolkits.skills_manager.toolkit.discover_github_skills",
        lambda fetcher, url: [
            skilly.Skill(name="new-skill", description="discovered", path="/fake")
        ],
    )
    mock_repo = MagicMock()
    mock_repo.find.return_value = None
    mock_repo.install.return_value = skilly.Skill(
        name="new-skill", description="installed", path="/fake"
    )
    monkeypatch.setattr(
        skills_manager_toolkit, "_get_repo", AsyncMock(return_value=mock_repo)
    )
    monkeypatch.setattr(
        "microclaw.toolkits.skills_manager.toolkit.interrupt",
        lambda *a, **kw: DecisionEnum.APPROVE.value,
    )

    result = await skills_manager_toolkit.install_skill("new-skill")
    assert "installed" in result.lower()


@pytest.mark.asyncio
async def test_remove_skill(skills_manager_toolkit, toolkit_context, monkeypatch):
    from microclaw.toolkits.enums import PermissionModeEnum
    skills_manager_toolkit.arguments.remove_mode = PermissionModeEnum.ALLOW

    mock_repo = MagicMock()
    mock_repo.find.return_value = skilly.Skill(name="old", description="", path="/fake")
    monkeypatch.setattr(
        skills_manager_toolkit, "_get_repo", AsyncMock(return_value=mock_repo)
    )
    result = await skills_manager_toolkit.remove_skill("old")
    assert "removed" in result.lower()


@pytest.mark.asyncio
async def test_update_skill__success(skills_manager_toolkit, toolkit_context, monkeypatch):
    from microclaw.toolkits.enums import PermissionModeEnum
    skills_manager_toolkit.arguments.update_mode = PermissionModeEnum.ALLOW

    mock_repo = MagicMock()
    mock_repo.find.return_value = skilly.Skill(name="up", description="", path="/fake")
    mock_repo.install.return_value = skilly.Skill(name="up", description="updated", path="/fake")
    monkeypatch.setattr(
        skills_manager_toolkit, "_get_repo", AsyncMock(return_value=mock_repo)
    )

    def mock_mp_search(self, query):
        m = MagicMock()
        m.name = "up"
        m.github_url = "https://github.com/user/up"
        return MagicMock(data=MagicMock(skills=[m]))
    monkeypatch.setattr(
        "microclaw.toolkits.skills_manager.toolkit.SkillsMp.search", mock_mp_search
    )
    monkeypatch.setattr(
        "microclaw.toolkits.skills_manager.toolkit.discover_github_skills",
        lambda fetcher, url: [skilly.Skill(name="up", description="updated", path="/fake")],
    )

    result = await skills_manager_toolkit.update_skill("up")
    assert "updated" in result.lower()


@pytest.mark.asyncio
async def test_enable_skill__success(skills_manager_toolkit, toolkit_context, users_storage):
    from microclaw.toolkits.context import TOOLKIT_CONTEXT
    from microclaw.toolkits.enums import PermissionModeEnum
    skills_manager_toolkit.arguments.enable_mode = PermissionModeEnum.ALLOW

    ctx = ToolkitExecutionContext(
        session_id=toolkit_context.session_id,
        request_id=toolkit_context.request_id,
        channel_key=toolkit_context.channel_key,
        channel_internal_id=toolkit_context.channel_internal_id,
        current_user_accessor=toolkit_context.current_user_accessor,
        all_skills={"global-skill": DiscoveryInfo(name="global-skill", description="desc")},
    )
    token = TOOLKIT_CONTEXT.set(ctx)
    try:
        result = await skills_manager_toolkit.enable_skill("global-skill")
        assert "enabled" in result.lower()
        user = await users_storage.get_user(
            filter_=UserFilter(id={toolkit_context.current_user_accessor.user_id})
        )
        agent = AgentSettings.model_validate(user.agent)
        assert any(
            (s.name if hasattr(s, "name") else s) == "global-skill" for s in agent.skills
        )
    finally:
        TOOLKIT_CONTEXT.reset(token)


@pytest.mark.asyncio
async def test_add_skill_to_my_agent(skills_manager_toolkit, toolkit_context, users_storage, monkeypatch):
    from microclaw.toolkits.enums import PermissionModeEnum
    skills_manager_toolkit.arguments.enable_mode = PermissionModeEnum.ALLOW

    mock_repo = MagicMock()
    mock_repo.find.return_value = skilly.Skill(name="cool", description="", path="/fake")
    monkeypatch.setattr(
        skills_manager_toolkit, "_get_repo", AsyncMock(return_value=mock_repo)
    )
    result = await skills_manager_toolkit.add_skill_to_my_agent("cool")
    assert "added" in result.lower()


@pytest.mark.asyncio
async def test_remove_skill_from_my_agent(skills_manager_toolkit, toolkit_context, users_storage):
    from microclaw.toolkits.enums import PermissionModeEnum
    skills_manager_toolkit.arguments.remove_mode = PermissionModeEnum.ALLOW
    uid = toolkit_context.current_user_accessor.user_id
    async for _ in users_storage.update_users(
        filter_=UserFilter(id={uid}),
        data=UserUpdate(agent=AgentSettings(skills=["cool"]).model_dump(mode="json")),
    ):
        pass
    result = await skills_manager_toolkit.remove_skill_from_my_agent("cool")
    assert "removed" in result.lower()


# ─── source_mode checks ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_install_skill__global_denied(skills_manager_toolkit, toolkit_context):
    from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum
    skills_manager_toolkit.arguments.source_mode = SourceModeEnum.GLOBAL
    skills_manager_toolkit.arguments.install_mode = PermissionModeEnum.ALLOW
    with pytest.raises(PermissionError):
        await skills_manager_toolkit.install_skill("any")


@pytest.mark.asyncio
async def test_install_skill__empty_denied(skills_manager_toolkit, toolkit_context):
    from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum
    skills_manager_toolkit.arguments.source_mode = SourceModeEnum.EMPTY
    skills_manager_toolkit.arguments.install_mode = PermissionModeEnum.ALLOW
    with pytest.raises(PermissionError):
        await skills_manager_toolkit.install_skill("any")


@pytest.mark.asyncio
async def test_update_skill__empty_denied(skills_manager_toolkit, toolkit_context):
    from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum
    skills_manager_toolkit.arguments.source_mode = SourceModeEnum.EMPTY
    skills_manager_toolkit.arguments.update_mode = PermissionModeEnum.ALLOW

    mock_repo = MagicMock()
    mock_repo.find.return_value = skilly.Skill(name="old", description="", path="/fake")

    async def fake_get_repo():
        return mock_repo
    import microclaw.toolkits.skills_manager.toolkit
    microclaw.toolkits.skills_manager.toolkit.SkillsManagerToolKit._get_repo = fake_get_repo

    with pytest.raises(PermissionError):
        await skills_manager_toolkit.update_skill("old")
    del microclaw.toolkits.skills_manager.toolkit.SkillsManagerToolKit._get_repo


@pytest.mark.asyncio
async def test_enable_skill__marketplace_denied(skills_manager_toolkit, toolkit_context):
    from microclaw.toolkits.context import TOOLKIT_CONTEXT
    from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum
    skills_manager_toolkit.arguments.enable_mode = PermissionModeEnum.ALLOW
    skills_manager_toolkit.arguments.source_mode = SourceModeEnum.MARKETPLACE

    ctx = ToolkitExecutionContext(
        session_id=toolkit_context.session_id,
        request_id=toolkit_context.request_id,
        channel_key=toolkit_context.channel_key,
        channel_internal_id=toolkit_context.channel_internal_id,
        current_user_accessor=toolkit_context.current_user_accessor,
        all_skills={"global-skill": DiscoveryInfo(name="global-skill", description="desc")},
    )
    token = TOOLKIT_CONTEXT.set(ctx)
    try:
        with pytest.raises(PermissionError):
            await skills_manager_toolkit.enable_skill("global-skill")
    finally:
        TOOLKIT_CONTEXT.reset(token)


@pytest.mark.asyncio
async def test_enable_skill__empty_denied(skills_manager_toolkit, toolkit_context):
    from microclaw.toolkits.context import TOOLKIT_CONTEXT
    from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum
    skills_manager_toolkit.arguments.enable_mode = PermissionModeEnum.ALLOW
    skills_manager_toolkit.arguments.source_mode = SourceModeEnum.EMPTY

    ctx = ToolkitExecutionContext(
        session_id=toolkit_context.session_id,
        request_id=toolkit_context.request_id,
        channel_key=toolkit_context.channel_key,
        channel_internal_id=toolkit_context.channel_internal_id,
        current_user_accessor=toolkit_context.current_user_accessor,
        all_skills={"global-skill": DiscoveryInfo(name="global-skill", description="desc")},
    )
    token = TOOLKIT_CONTEXT.set(ctx)
    try:
        with pytest.raises(PermissionError):
            await skills_manager_toolkit.enable_skill("global-skill")
    finally:
        TOOLKIT_CONTEXT.reset(token)


# ─── cross-user ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enable_skill__cross_user(admin_context, users_storage, skills_manager_toolkit):
    from microclaw.toolkits.enums import PermissionModeEnum
    skills_manager_toolkit.arguments.enable_mode = PermissionModeEnum.ALLOW
    context, target_user, admin_user = admin_context

    result = await skills_manager_toolkit.enable_skill("global_skill", user_id=str(target_user.id))
    assert "enabled" in result.lower()

    target = await users_storage.get_user(filter_=UserFilter(id={target_user.id}))
    agent = AgentSettings.model_validate(target.agent)
    assert any(
        (s.name if hasattr(s, "name") else s) == "global_skill" for s in agent.skills
    )


@pytest.mark.asyncio
async def test_list_my_skills__cross_user(admin_context, skills_manager_toolkit):
    from microclaw.toolkits.enums import PermissionModeEnum
    skills_manager_toolkit.arguments.enable_mode = PermissionModeEnum.ALLOW
    context, target_user, admin_user = admin_context

    await skills_manager_toolkit.enable_skill("global_skill", user_id=str(target_user.id))
    result = await skills_manager_toolkit.list_my_skills(user_id=str(target_user.id))
    assert result == ["global_skill"]


@pytest.mark.asyncio
async def test_cross_user__no_accessor_denied(skills_manager_toolkit, toolkit_context, users_storage):
    from microclaw.toolkits.enums import PermissionModeEnum
    skills_manager_toolkit.arguments.enable_mode = PermissionModeEnum.ALLOW
    other = await users_storage.create_user(data=UserCreate(role=UserRoleEnum.USER))
    with pytest.raises(PermissionError, match="Cross-user access not granted"):
        await skills_manager_toolkit.enable_skill("global_skill", user_id=str(other.id))


@pytest.mark.asyncio
async def test_cross_user__read_only_denied(admin_context, skills_manager_toolkit):
    from microclaw.toolkits.enums import PermissionModeEnum
    skills_manager_toolkit.arguments.enable_mode = PermissionModeEnum.ALLOW
    context, target_user, admin_user = admin_context

    context_readonly = ToolkitExecutionContext(
        session_id=context.session_id,
        request_id=context.request_id,
        channel_key=context.channel_key,
        channel_internal_id=context.channel_internal_id,
        current_user_accessor=context.current_user_accessor,
        all_users_accessor=AllUsersAccessor(
            storage=context.current_user_accessor._storage, writable=False
        ),
        all_skills=context.all_skills,
    )
    token = TOOLKIT_CONTEXT.set(context_readonly)
    try:
        with pytest.raises(PermissionError, match="Cross-user write access not granted"):
            await skills_manager_toolkit.enable_skill("global_skill", user_id=str(target_user.id))
    finally:
        TOOLKIT_CONTEXT.reset(token)
