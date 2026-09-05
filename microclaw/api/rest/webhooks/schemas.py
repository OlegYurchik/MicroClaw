from typing import Any, Self
import uuid

from pydantic import BaseModel, Field

from microclaw.api.rest.schemas import ListResponse
from microclaw.dto import Webhook


class WebhookCreateRequest(BaseModel):
    path: str
    enabled: bool = True
    args: dict[str, Any] = Field(default_factory=dict)
    user_id: uuid.UUID | None = None
    agent: str | None = None
    channel: str | None = None
    channel_internal_id: str | None = None


class WebhookResponse(BaseModel):
    id: uuid.UUID
    path: str
    enabled: bool
    args: dict[str, Any]
    agent: str | None = None
    channel: str | None = None
    channel_internal_id: str | None = None

    @classmethod
    def from_item(cls, item: Webhook) -> Self:
        return cls(
            id=item.id,
            path=item.path,
            enabled=item.enabled,
            args=item.args,
            agent=item.agent,
            channel=item.channel,
            channel_internal_id=item.channel_internal_id,
        )


class WebhookListResponse(ListResponse[WebhookResponse]):

    @classmethod
    def from_items(cls, items: list[Webhook]) -> Self:
        return cls(
            data=[WebhookResponse.from_item(item=item) for item in items],
            total=len(items),
        )
