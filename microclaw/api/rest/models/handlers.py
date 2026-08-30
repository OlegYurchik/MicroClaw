from .schemas import ModelListResponse, ModelResponse
import fastapi

from microclaw.api.rest.dependencies import auth as auth_dependency
from microclaw.api.rest.dependencies import resolver
from microclaw.api.rest.exceptions import HTTPNotFound
from microclaw.resolver import DependencyResolver


async def list_models(
        _: None = fastapi.Depends(auth_dependency),
        resolver: DependencyResolver = fastapi.Depends(resolver),
) -> ModelListResponse:
    return ModelListResponse.from_items(
        items=list(resolver.settings.models.items()),
    )


async def get_model(
        id: str,
        _: None = fastapi.Depends(auth_dependency),
        resolver: DependencyResolver = fastapi.Depends(resolver),
) -> ModelResponse:
    settings = resolver.settings.models.get(id)
    if settings is None:
        raise HTTPNotFound(detail="Model not found")
    return ModelResponse.from_item(item=(id, settings))
