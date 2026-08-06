from typing import Any

from pydantic import BaseModel, Field

from .capabilities import DiscoveryCapability, ToolKitCapability


class ToolKitSettings(BaseModel):
    path: str
    name: str | None = None
    prefix: str = ""
    prompt: str | None = None
    required_capabilities: list[ToolKitCapability] | None = None
    write_capabilities: list[ToolKitCapability] | None = None
    discovery_capabilities: list[DiscoveryCapability] | None = None
    args: dict[str, Any] = Field(default_factory=dict)
