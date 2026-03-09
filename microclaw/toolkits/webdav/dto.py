from datetime import datetime
from pydantic import BaseModel, Field


class WebDAVObject(BaseModel):
    """Base class for WebDAV objects (files and directories)."""
    path: str = Field(description="Full path to the object")
    name: str = Field(description="Object name")
    last_modified: datetime | None = Field(default=None, description="Last modification timestamp")


class File(WebDAVObject):
    """Represents a file in WebDAV storage."""
    size: int | None = Field(default=None, description="File size in bytes")
    content_type: str | None = Field(default=None, description="MIME type of the file")
    etag: str | None = Field(default=None, description="Entity tag for cache validation")


class Directory(WebDAVObject):
    """Represents a directory in WebDAV storage."""
