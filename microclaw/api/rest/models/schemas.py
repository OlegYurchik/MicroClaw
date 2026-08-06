from typing import Any, Self

from pydantic import BaseModel

from microclaw.api.rest.schemas import ListResponse


class ModelCostsResponse(BaseModel):
    input: float = 0
    output: float = 0
    cache_read: float = 0
    cache_write: float = 0
    audio_input: float = 0
    audio_output: float = 0
    currency: str = "$"


class ModelResponse(BaseModel):
    id: str
    model_id: str
    provider: str | None
    costs: ModelCostsResponse | None

    @classmethod
    def from_item(cls, item: tuple[str, Any]) -> Self:
        name, settings = item
        return cls(
            id=name,
            model_id=settings.id,
            provider=(
                settings.provider.base_url
                if hasattr(settings.provider, "base_url")
                else settings.provider
            ),
            costs=(
                ModelCostsResponse(**settings.costs.model_dump())
                if settings.costs
                else None
            ),
        )


class ModelListResponse(ListResponse[ModelResponse]):

    @classmethod
    def from_items(cls, items: list[tuple[str, Any]]) -> Self:
        return cls(
            data=[ModelResponse.from_item(item=item) for item in items],
            total=len(items),
        )
