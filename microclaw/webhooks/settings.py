from typing import Any

from pydantic import BaseModel, Field


class WebhookSettings(BaseModel):
    path: str
    enabled: bool = True
    args: dict[str, Any] = Field(default_factory=dict)
