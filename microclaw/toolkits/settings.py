from typing import Any

from pydantic import BaseModel, Field


class ToolKitSettings(BaseModel):
    path: str
    prefix: str = ""
    prompt: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)