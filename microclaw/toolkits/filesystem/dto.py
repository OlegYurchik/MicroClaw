import enum
from pydantic import BaseModel


class FilesystemItemType(str, enum.Enum):
    """Type of filesystem item."""

    FILE = "file"
    DIRECTORY = "directory"


class DirectoryInfo(BaseModel):
    """Information about a file or directory."""

    name: str
    type: FilesystemItemType
    size: int | None
    modified: float
