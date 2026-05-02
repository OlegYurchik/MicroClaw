import pathlib
from typing import Any

from pydantic import BaseModel, Field

from microclaw.toolkits.enums import PermissionModeEnum


class FileSystemToolKitSettings(BaseModel):
    """Settings for the filesystem toolkit."""

    directories: list[str] = Field(
        default_factory=lambda: [str(pathlib.Path.cwd() / ".filesystem")],
        description="List of allowed directories for file operations",
    )
    write_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
