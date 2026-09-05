import uuid

from pydantic import AwareDatetime
from pydantic_filters import BaseFilter


class UserFilter(BaseFilter):
    id: set[uuid.UUID]
    role: set[str]


class WebhookFilter(BaseFilter):
    id: set[uuid.UUID]
    user_id: set[uuid.UUID]
    enabled: bool | None = None
    agent: set[str]
    channel: set[str]
    channel_internal_id: set[str]


class CronFilter(BaseFilter):
    id: set[uuid.UUID]
    user_id: set[uuid.UUID]
    enabled: bool | None = None


class TokenFilter(BaseFilter):
    token: set[str]
    user_id: set[uuid.UUID]
    expires_at: AwareDatetime | None = None
    expires_at__gt: AwareDatetime | None = None
    expires_at__lt: AwareDatetime | None = None


class UserChannelFilter(BaseFilter):
    user_id: set[uuid.UUID]
    channel_key: set[str]
    channel_internal_id: set[str]
    actual_session_id: set[uuid.UUID]


class SessionFilter(BaseFilter):
    id: set[uuid.UUID]
    user_id: set[uuid.UUID]
    channel_key: set[str]
    channel_internal_id: set[str]
