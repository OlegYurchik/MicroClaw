import datetime
import uuid
from typing import Self

from pydantic import BaseModel

from microclaw.api.rest.schemas import ListResponse
from microclaw.dto import SessionMetadata, Spending


class SessionResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime.datetime | None
    updated_at: datetime.datetime | None
    context_size: int
    spending: Spending | None

    @classmethod
    def from_item(cls, item: SessionMetadata) -> Self:
        return cls(
            id=item.id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            context_size=item.context_size,
            spending=item.spending,
        )


class SessionListResponse(ListResponse[SessionResponse]):

    @classmethod
    def from_items(cls, items: list[SessionMetadata]) -> Self:
        return cls(
            data=[SessionResponse.from_item(item=item) for item in items],
            total=len(items),
        )
