import fastapi

from microclaw.api.rest.dependencies import auth as auth_dependency
from microclaw.api.rest.dependencies import resolver
from microclaw.api.rest.exceptions import HTTPNotFound
from microclaw.resolver import DependencyResolver

from .schemas import AgentListResponse, AgentResponse


async def list_agents(
        _: None = fastapi.Depends(auth_dependency),
        resolver: DependencyResolver = fastapi.Depends(resolver),
) -> AgentListResponse:
    return AgentListResponse.from_items(
        items=list(resolver.settings.agents.items()),
    )


async def get_agent(
        id: str,
        _: None = fastapi.Depends(auth_dependency),
        resolver: DependencyResolver = fastapi.Depends(resolver),
) -> AgentResponse:
    settings = resolver.settings.agents.get(id)
    if settings is None:
        raise HTTPNotFound(detail="Agent not found")
    return AgentResponse.from_item(item=(id, settings))
