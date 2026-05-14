import uuid
from typing import Any, Iterable, Self

from pydantic import AwareDatetime, BaseModel, Field

from microclaw.api.rest.schemas import ListResponse
from microclaw.dto import User, UserRoleEnum
from microclaw.utils import Empty


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


class UserCreateRequest(BaseModel):
    role: UserRoleEnum = UserRoleEnum.USER
    agent: dict[str, Any] | None = None


class UserUpdateRequest(BaseModel):
    role: UserRoleEnum | Empty = Empty
    agent: dict[str, Any] | None | Empty = Empty


class UserListResponse(ListResponse):
    data: list[UserResponse]

    @classmethod
    def from_items(cls, items: Iterable[User]) -> Self:
        return cls(
            data=[UserResponse.from_item(item=item) for item in items],
        )


class TokenCreateRequest(BaseModel):
    ttl_days: int | None = Field(default=30, ge=1)


class TokenResponse(BaseModel):
    token: str
    expires_at: AwareDatetime | None
