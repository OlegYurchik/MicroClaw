import uuid
from datetime import date

from pydantic_filters import BaseFilter


class SessionFilter(BaseFilter):
    id: uuid.UUID | None = None
    created_at: date | None = None


class MessageFilter(BaseFilter):
    session_id: uuid.UUID | None = None
