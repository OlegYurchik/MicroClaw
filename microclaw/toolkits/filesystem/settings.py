import pathlib
from typing import Any

from pydantic import BaseModel, Field


class FileSystemToolKitSettings(BaseModel):
    """Settings for the filesystem toolkit."""

    directories: list[str] = Field(
        default_factory=lambda: [str(pathlib.Path.cwd() / ".filesystem")],
        description="List of allowed directories for file operations",
    )
    allow_write: bool = Field(
        default=False,
        description="Allow writing files to disk",
    )
