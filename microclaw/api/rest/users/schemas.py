from collections.abc import Iterable
from typing import Any, Self
import uuid

from pydantic import BaseModel, Field

from microclaw.api.rest.schemas import ListResponse, UserResponse
from microclaw.dto import User, UserRoleEnum


class UserCreateRequest(BaseModel):
    role: UserRoleEnum = UserRoleEnum.USER
    agent: dict[str, Any] | None = None


class UserUpdateRequest(BaseModel):
    role: UserRoleEnum | None = None
    agent: dict[str, Any] | None = None


class UserListResponse(ListResponse[UserResponse]):

    @classmethod
    def from_items(cls, items: Iterable[User]) -> Self:
        return cls(
            data=[UserResponse.from_item(item=item) for item in items],
            total=len(list(items)),
        )


class UserSessionsResponse(ListResponse[uuid.UUID]):

    @classmethod
    def from_items(cls, items: list[uuid.UUID]) -> Self:
        return cls(
            data=items,
            total=len(items),
        )


class TokenCreateRequest(BaseModel):
    ttl_days: int | None = Field(default=30, ge=1)
