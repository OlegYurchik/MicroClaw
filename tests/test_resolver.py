import pytest

from microclaw.agents import Agent, APITypeEnum, ModelSettings, ProviderSettings
from microclaw.resolver import DependencyResolver
from microclaw.settings import MicroclawSettings


@pytest.mark.asyncio
async def test_resolve_agent_passes_syncer(tmp_path):
    settings = MicroclawSettings(
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
        skills_dir=tmp_path,
    )
    resolver = DependencyResolver(settings=settings)
    agents = await resolver.resolve_agents()
    assert "default" in agents
    assert isinstance(agents["default"], Agent)
