from pydantic import BaseModel, Field


class WebDAVSettings(BaseModel):
    """Settings for connecting to a WebDAV server."""
    
    url: str = Field(
        description=(
            "URL of the WebDAV server "
            "(e.g., https://webdav.example.com/dav)"
        ),
    )
    username: str = Field(description="Username for authentication")
    password: str = Field(description="Password or app password for authentication")
    verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificate (default: True)",
    )
