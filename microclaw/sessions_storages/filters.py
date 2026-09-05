import uuid

from pydantic import AwareDatetime
from pydantic_filters import BaseFilter


class SessionFilter(BaseFilter):
    id: set[uuid.UUID]
    created_at: set[AwareDatetime]
    updated_at: set[AwareDatetime]
    channel_key: set[str]
    created_at__gt: AwareDatetime
    created_at__lt: AwareDatetime
    updated_at__gt: AwareDatetime
    updated_at__lt: AwareDatetime


class MessageFilter(BaseFilter):
    id: set[uuid.UUID]
    session_id: set[uuid.UUID]
    created_at: set[AwareDatetime]
    role: set[str]
