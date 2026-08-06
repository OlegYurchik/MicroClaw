import uuid

from pydantic_filters import BaseFilter


class UserFilter(BaseFilter):
    id: uuid.UUID | None = None
    role: str | None = None
