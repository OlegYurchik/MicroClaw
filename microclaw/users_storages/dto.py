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
    "WebhookCreate",
    "WebhookUpdate",
)


class UserCreate(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    role: UserRoleEnum = UserRoleEnum.USER
    agent: dict[str, Any] | None = None


class UserUpdate(BaseModel):
    role: UserRoleEnum | None = None
    agent: dict[str, Any] | None = None


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
    token: str | None = Field(default=None)
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


class WebhookCreate(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    path: str
    enabled: bool = True
    args: dict[str, Any] = Field(default_factory=dict)
    agent: str | None = None
    channel: str | None = None
    channel_internal_id: str | None = None


class WebhookUpdate(BaseModel):
    path: str | None = None
    enabled: bool | None = None
    args: dict[str, Any] | None = None
    agent: str | None = None
    channel: str | None = None
    channel_internal_id: str | None = None
