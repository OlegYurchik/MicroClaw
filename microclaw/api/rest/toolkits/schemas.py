from typing import Any, Self

from pydantic import BaseModel

from microclaw.api.rest.schemas import ListResponse


class ToolkitResponse(BaseModel):
    id: str
    path: str

    @classmethod
    def from_item(cls, item: tuple[str, Any]) -> Self:
        name, settings = item
        return cls(
            id=name,
            path=settings.path,
        )


class ToolkitListResponse(ListResponse[ToolkitResponse]):

    @classmethod
    def from_items(cls, items: list[tuple[str, Any]]) -> Self:
        return cls(
            data=[ToolkitResponse.from_item(item=item) for item in items],
            total=len(items),
        )
