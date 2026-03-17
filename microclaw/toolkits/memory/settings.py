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
