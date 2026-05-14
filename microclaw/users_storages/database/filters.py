import uuid

from pydantic_filters import BaseFilter


class UserFilter(BaseFilter):
    id: uuid.UUID | None = None


class SessionFilter(BaseFilter):
    id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    channel_key: str | None = None
    channel_internal_id: str | None = None


class CronFilter(BaseFilter):
    id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None


class TokenFilter(BaseFilter):
    token: str | None = None
    user_id: uuid.UUID | None = None
