import base64
import json
from typing import Any, Generic, Self, TypeVar
import uuid

from pydantic import AwareDatetime, BaseModel, Field
from pydantic_filters import BaseSort, SortByOrder
from pydantic_filters.pagination import OffsetPagination

from microclaw.dto import User, UserRoleEnum


T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    data: list[T]
    total: int | None = None
    next_cursor: str | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    role: UserRoleEnum = UserRoleEnum.USER
    agent: dict[str, Any] | None = None

    @classmethod
    def from_item(cls, item: User) -> Self:
        return cls(
            id=item.id,
            role=item.role,
            agent=item.agent,
        )


class TokenResponse(BaseModel):
    token: str
    expires_at: AwareDatetime | None = None


class ListQueryParams(BaseModel):
    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    sort_by: str | None = None
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")

    @property
    def offset(self) -> int:
        if self.cursor is None:
            return 0
        try:
            decoded = base64.urlsafe_b64decode(self.cursor.encode()).decode()
            return json.loads(decoded).get("offset", 0)
        except Exception:
            return 0

    def get_sort(self):
        if self.sort_by is None:
            return None
        order = SortByOrder.asc if self.sort_order == "asc" else SortByOrder.desc
        return BaseSort(sort_by=self.sort_by, sort_by_order=order)

    def get_pagination(self):
        return OffsetPagination(offset=self.offset, limit=self.limit)

    def next_cursor(self, returned_count: int) -> str | None:
        next_offset = self.offset + returned_count
        payload = json.dumps({"offset": next_offset})
        return base64.urlsafe_b64encode(payload.encode()).decode()
