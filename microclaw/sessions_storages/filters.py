import uuid
from datetime import datetime

from pydantic_filters import BaseFilter, BaseSort, SortByOrder
from pydantic_filters.pagination import OffsetPagination as BasePagination


class SessionFilter(BaseFilter):
    id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MessageFilter(BaseFilter):
    id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    created_at: datetime | None = None
    role: str | None = None
    is_summary: bool | None = None