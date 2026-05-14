import uuid
from typing import Any

from pydantic import BaseModel, Field


class CronTask(BaseModel):
    id: uuid.UUID | None = None
    path: str
    cron: str
    enabled: bool
    args: dict[str, Any] = Field(default_factory=dict)
