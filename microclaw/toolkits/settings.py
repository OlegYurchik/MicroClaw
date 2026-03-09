from typing import Any

from pydantic import BaseModel, Field


class ToolKitSettings(BaseModel):
    path: str
    name: str | None = None
    prefix: str = ""
    extra_info: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)