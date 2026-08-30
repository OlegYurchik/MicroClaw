from datetime import timedelta
from typing import Any
import uuid

from pydantic import AwareDatetime, BaseModel, Field

from microclaw.dto import UserRoleEnum
from microclaw.utils import utcnow


__all__ = (
    "CronCreate",
    "CronUpdate",
    "TokenCreate",
    "TokenUpdate",
    "UserChannelCreate",
    "UserChannelUpdate",
    "UserCreate",
    "UserUpdate",
)


class UserCreate(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    role: UserRoleEnum = UserRoleEnum.USER
    agent: dict[str, Any] | str | None = None


class UserUpdate(BaseModel):
    role: UserRoleEnum | None = None
    agent: dict[str, Any] | str | None = None


class UserChannelCreate(BaseModel):
    user_id: uuid.UUID
    channel_key: str
    channel_internal_id: str
    actual_session_id: uuid.UUID | None = None


class UserChannelUpdate(BaseModel):
    user_id: uuid.UUID | None = None
    channel_key: str | None = None
    channel_internal_id: str | None = None
    actual_session_id: uuid.UUID | None = None


class TokenCreate(BaseModel):
    user_id: uuid.UUID
    expires_at: AwareDatetime | None = Field(
        default_factory=lambda: utcnow() + timedelta(days=90),
    )


class TokenUpdate(BaseModel):
    expires_at: AwareDatetime | None = None


class CronCreate(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    path: str
    cron: str
    enabled: bool = True
    args: dict[str, Any] = Field(default_factory=dict)


class CronUpdate(BaseModel):
    cron: str | None = None
    enabled: bool | None = None
    args: dict[str, Any] | None = None
