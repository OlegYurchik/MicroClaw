import uuid
from typing import Any, Self

from pydantic import BaseModel, Field, field_validator

from microclaw.api.rest.schemas import ListResponse
from microclaw.dto import CronTask


class CronTaskCreateRequest(BaseModel):
    path: str
    cron: str
    enabled: bool = True
    args: dict[str, Any] = Field(default_factory=dict)
    user_id: uuid.UUID | None = None

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, v: str) -> str:
        parts = v.split()
        if len(parts) != 5:
            raise ValueError("Invalid cron expression: expected 5 parts")
        return v


class CronTaskResponse(BaseModel):
    id: uuid.UUID
    path: str
    cron: str
    enabled: bool
    args: dict[str, Any]

    @classmethod
    def from_item(cls, item: CronTask) -> Self:
        return cls(
            id=item.id,
            path=item.path,
            cron=item.cron,
            enabled=item.enabled,
            args=item.args,
        )


class CronTaskListResponse(ListResponse[CronTaskResponse]):

    @classmethod
    def from_items(cls, items: list[CronTask]) -> Self:
        return cls(
            data=[CronTaskResponse.from_item(item=item) for item in items],
            total=len(items),
        )
