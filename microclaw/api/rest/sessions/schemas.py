from typing import Self
import uuid

from pydantic import AwareDatetime, BaseModel

from microclaw.api.rest.schemas import ListResponse
from microclaw.dto import Session, Spending


class SessionResponse(BaseModel):
    id: uuid.UUID
    created_at: AwareDatetime | None
    updated_at: AwareDatetime | None
    context_size: int
    spending: Spending | None

    @classmethod
    def from_item(cls, item: Session) -> Self:
        return cls(
            id=item.id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            context_size=item.context_size,
            spending=item.spending,
        )


class SessionListResponse(ListResponse[SessionResponse]):

    @classmethod
    def from_items(cls, items: list[Session]) -> Self:
        return cls(
            data=[SessionResponse.from_item(item=item) for item in items],
            total=len(items),
        )


class SpendingResponse(BaseModel):
    cost: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    audio_input_seconds: int
    audio_output_seconds: int
    currency: str

    @classmethod
    def from_spending(cls, spending: Spending | None) -> Self:
        if spending is None:
            return cls(
                cost=0.0,
                input_tokens=0,
                output_tokens=0,
                cache_read_tokens=0,
                cache_write_tokens=0,
                audio_input_seconds=0,
                audio_output_seconds=0,
                currency="$",
            )
        return cls(
            cost=spending.cost,
            input_tokens=spending.input_tokens,
            output_tokens=spending.output_tokens,
            cache_read_tokens=spending.cache_read_tokens,
            cache_write_tokens=spending.cache_write_tokens,
            audio_input_seconds=spending.audio_input_seconds,
            audio_output_seconds=spending.audio_output_seconds,
            currency=spending.currency,
        )
