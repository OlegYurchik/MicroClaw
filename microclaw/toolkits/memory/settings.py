import enum
import pathlib
from typing import Any, Literal

from pydantic import BaseModel, Field

from microclaw.toolkits.settings import ToolKitSettings
from .drivers import MemoryDriverSettingsType
from .drivers.filesystem import FilesystemMemoryDriverSettings


class MemoryToolKitSettings(BaseModel):
    """Settings for the memory toolkit."""

    driver: MemoryDriverSettingsType = Field(
        default_factory=FilesystemMemoryDriverSettings,
    )
    max_memory_tokens: int = Field(
        default=2000,
        ge=500,
        le=10000,
        description="Maximum tokens for memory file (applies to both general and daily)"
    )
