from .drivers import MemoryDriverSettingsType
from .drivers.filesystem import FilesystemMemoryDriverSettings
from pydantic import BaseModel, Field

from microclaw.toolkits.enums import PermissionModeEnum


class MemoryToolKitSettings(BaseModel):
    """Settings for the memory toolkit."""

    driver: MemoryDriverSettingsType = Field(
        default_factory=FilesystemMemoryDriverSettings,
    )
    max_memory_tokens: int = Field(
        default=2000,
        ge=500,
        le=10000,
        description="Maximum tokens for memory file (applies to both general and daily)",
    )
    edit_mode: PermissionModeEnum = PermissionModeEnum.ALLOW
