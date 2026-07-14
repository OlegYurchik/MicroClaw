import pathlib

import pytest
import skilly
from skilly.skillsmp.client import (
    SkillsMpFilters,
    SkillsMpPagination,
    SkillsMpSearchData,
    SkillsMpSearchResult,
    SkillsMpSkill,
)

from microclaw.agents import (
    Agent,
    AgentSettings,
    APITypeEnum,
    ModelSettings,
    ProviderSettings,
    SkillSettings,
)
from microclaw.resolver import DependencyResolver
from microclaw.settings import MicroclawSettings
from microclaw.skills import SkillRepositoryGitHubSettings, SkillRepositoryLocalSettings


@pytest.fixture
def base_settings(tmp_path):
    return MicroclawSettings(
        providers={
            "default": ProviderSettings(
                base_url="http://localhost:11434",
                api_type=APITypeEnum.OLLAMA,
            )
        },
        models={
            "default": ModelSettings(
                id="gpt-4",
                provider="default",
            )
        },
        skills_directory=tmp_path,
    )


@pytest.mark.asyncio
async def test_resolve_agent_passes_syncer(base_settings):
    resolver = DependencyResolver(settings=base_settings)
    agents = await resolver.resolve_agents()
    assert "default" in agents
    assert isinstance(agents["default"], Agent)


@pytest.mark.asyncio
async def test_resolve_skill_already_installed(base_settings, monkeypatch):
    skill = skilly.Skill(
        name="installed-skill",
        description="test",
        path=str(base_settings.skills_directory / "installed-skill"),
    )
    monkeypatch.setattr(
        "microclaw.resolver.skilly.SkillRepository.find", lambda *a, **kw: skill
    )

    resolver = DependencyResolver(settings=base_settings)
    result = await resolver.resolve_skill(SkillSettings(name="installed-skill"))
    assert result == str(base_settings.skills_directory / "installed-skill")


@pytest.mark.asyncio
async def test_resolve_skill_local_repo(base_settings, tmp_path):
    src_dir = tmp_path / "src" / "my-skill"
    src_dir.mkdir(parents=True)
    (src_dir / "skill.md").write_text(
        "---\nname: my-skill\ndescription: test\n---\n\n# Skill\n"
    )

    settings = base_settings.model_copy()
    settings.skills_directory = tmp_path / "skills"
    settings.skills_repositories = {
        "local_repo": SkillRepositoryLocalSettings(directory=tmp_path / "src")
    }

    resolver = DependencyResolver(settings=settings)
    result = await resolver.resolve_skill(
        SkillSettings(name="my-skill", repo="local_repo")
    )
    assert result is not None
    assert (pathlib.Path(result) / "skill.md").exists()


@pytest.mark.asyncio
async def test_resolve_skill_local_repo_not_found(base_settings, tmp_path):
    settings = base_settings.model_copy()
    settings.skills_repositories = {
        "local_repo": SkillRepositoryLocalSettings(directory=tmp_path / "src")
    }

    resolver = DependencyResolver(settings=settings)
    result = await resolver.resolve_skill(
        SkillSettings(name="missing-skill", repo="local_repo")
    )
    assert result is None


@pytest.mark.asyncio
async def test_resolve_skill_github_repo(base_settings, monkeypatch):
    discovered_skill = skilly.Skill(
        name="github-skill",
        description="from github",
        path="/fake/path/github-skill",
    )

    def mock_discover(fetcher, url, **kwargs):
        return [discovered_skill]

    monkeypatch.setattr(
        "microclaw.resolver.discover_github_skills", mock_discover
    )

    installed_skill = skilly.Skill(
        name="github-skill",
        description="installed",
        path=str(base_settings.skills_directory / "github-skill"),
    )
    monkeypatch.setattr(
        "microclaw.resolver.skilly.SkillRepository.install",
        lambda *a, **kw: installed_skill,
    )
    monkeypatch.setattr(
        "microclaw.resolver.skilly.SkillRepository.find", lambda *a, **kw: None
    )

    settings = base_settings.model_copy()
    settings.skills_repositories = {
        "gh_repo": SkillRepositoryGitHubSettings(url="https://github.com/user/skills")
    }

    resolver = DependencyResolver(settings=settings)
    result = await resolver.resolve_skill(
        SkillSettings(name="github-skill", repo="gh_repo")
    )
    assert result == str(base_settings.skills_directory / "github-skill")


@pytest.mark.asyncio
async def test_resolve_skill_github_repo_not_found(base_settings, monkeypatch):
    monkeypatch.setattr(
        "microclaw.resolver.discover_github_skills", lambda *a, **kw: []
    )
    monkeypatch.setattr(
        "microclaw.resolver.skilly.SkillRepository.find", lambda *a, **kw: None
    )

    settings = base_settings.model_copy()
    settings.skills_repositories = {
        "gh_repo": SkillRepositoryGitHubSettings(url="https://github.com/user/skills")
    }

    resolver = DependencyResolver(settings=settings)
    result = await resolver.resolve_skill(
        SkillSettings(name="missing-skill", repo="gh_repo")
    )
    assert result is None


def _make_search_result(skills_list):
    return SkillsMpSearchResult(
        success=True,
        data=SkillsMpSearchData(
            skills=skills_list,
            pagination=SkillsMpPagination(
                page=1, limit=20, total=len(skills_list), total_pages=1, has_next=False, has_prev=False, total_is_exact=True
            ),
            filters=SkillsMpFilters(search="test", sort_by="stars"),
        ),
    )


@pytest.mark.asyncio
async def test_resolve_skill_skillsmp_fallback(base_settings, monkeypatch):
    discovered_skill = skilly.Skill(
        name="mp-skill",
        description="from marketplace",
        path="/fake/path/mp-skill",
    )

    def mock_search(self, query):
        return _make_search_result(
            [
                SkillsMpSkill(
                    id="1",
                    name="mp-skill",
                    author="test",
                    description="test",
                    github_url="https://github.com/user/mp-skill",
                    skill_url="https://skillsmp.com/mp-skill",
                )
            ]
        )

    monkeypatch.setattr("microclaw.resolver.SkillsMp.search", mock_search)
    monkeypatch.setattr(
        "microclaw.resolver.discover_github_skills",
        lambda *a, **kw: [discovered_skill],
    )

    installed_skill = skilly.Skill(
        name="mp-skill",
        description="installed",
        path=str(base_settings.skills_directory / "mp-skill"),
    )
    monkeypatch.setattr(
        "microclaw.resolver.skilly.SkillRepository.install",
        lambda *a, **kw: installed_skill,
    )
    monkeypatch.setattr(
        "microclaw.resolver.skilly.SkillRepository.find", lambda *a, **kw: None
    )

    resolver = DependencyResolver(settings=base_settings)
    result = await resolver.resolve_skill(SkillSettings(name="mp-skill"))
    assert result == str(base_settings.skills_directory / "mp-skill")


@pytest.mark.asyncio
async def test_resolve_skill_skillsmp_not_found(base_settings, monkeypatch):
    def mock_search(self, query):
        return _make_search_result([])

    monkeypatch.setattr("microclaw.resolver.SkillsMp.search", mock_search)
    monkeypatch.setattr(
        "microclaw.resolver.skilly.SkillRepository.find", lambda *a, **kw: None
    )

    resolver = DependencyResolver(settings=base_settings)
    result = await resolver.resolve_skill(SkillSettings(name="missing-skill"))
    assert result is None


@pytest.mark.asyncio
async def test_resolve_skills_batch_filters_none(base_settings, monkeypatch):
    resolver = DependencyResolver(settings=base_settings)

    call_count = 0
    async def mock_resolve(skill_item, repo=None):
        nonlocal call_count
        call_count += 1
        if isinstance(skill_item, SkillSettings) and skill_item.name == "found-skill":
            return str(base_settings.skills_directory / "found-skill")
        return None

    monkeypatch.setattr(resolver, "resolve_skill", mock_resolve)

    agent_settings = AgentSettings(
        skills=[
            SkillSettings(name="found-skill"),
            SkillSettings(name="not-found-skill"),
        ]
    )

    result = await resolver.resolve_skills(agent_settings)
    assert result == [str(base_settings.skills_directory / "found-skill")]
    assert call_count == 2


def test_normalize_skill_as_is(base_settings):
    resolver = DependencyResolver(settings=base_settings)
    skill = SkillSettings(name="my-skill", repo="local")
    assert resolver._normalize_skill(skill) == skill


def test_normalize_skill_from_global_skillsettings(base_settings):
    settings = base_settings.model_copy()
    settings.skills = {"alias": SkillSettings(name="real-skill", repo="local")}
    resolver = DependencyResolver(settings=settings)
    result = resolver._normalize_skill("alias")
    assert result.name == "real-skill"
    assert result.repo == "local"


def test_normalize_skill_from_global_str(base_settings):
    settings = base_settings.model_copy()
    settings.skills = {"alias": "real-skill"}
    resolver = DependencyResolver(settings=settings)
    result = resolver._normalize_skill("alias")
    assert result.name == "real-skill"
    assert result.repo is None


def test_normalize_skill_unknown(base_settings):
    resolver = DependencyResolver(settings=base_settings)
    result = resolver._normalize_skill("unknown-skill")
    assert result.name == "unknown-skill"
    assert result.repo is None
