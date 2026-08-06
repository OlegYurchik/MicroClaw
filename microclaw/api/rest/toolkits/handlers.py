import fastapi

from microclaw.api.rest.dependencies import auth as auth_dependency
from microclaw.api.rest.dependencies import resolver
from microclaw.api.rest.exceptions import HTTPNotFound
from microclaw.resolver import DependencyResolver

from .schemas import ToolkitListResponse, ToolkitResponse


async def list_toolkits(
        _: None = fastapi.Depends(auth_dependency),
        resolver: DependencyResolver = fastapi.Depends(resolver),
) -> ToolkitListResponse:
    return ToolkitListResponse.from_items(
        items=list(resolver.settings.toolkits.items()),
    )


async def get_toolkit(
        id: str,
        _: None = fastapi.Depends(auth_dependency),
        resolver: DependencyResolver = fastapi.Depends(resolver),
) -> ToolkitResponse:
    settings = resolver.settings.toolkits.get(id)
    if settings is None:
        raise HTTPNotFound(detail="Toolkit not found")
    return ToolkitResponse.from_item(item=(id, settings))
