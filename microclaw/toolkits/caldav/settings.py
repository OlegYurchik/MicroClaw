from pydantic import BaseModel, Field


class CalDAVSettings(BaseModel):
    """Settings for connecting to a CalDAV server."""
    
    url: str = Field(
        description=(
            "URL of the CalDAV server "
            "(e.g., https://calendar.google.com/dav/user@gmail.com/calendar)"
        ),
    )
    username: str = Field(description="Username for authentication")
    password: str = Field(description="Password or app password for authentication")
    verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificate (default: True)",
    )
    default_calendar_path: str | None = Field(
        default=None,
        description="Path to the default calendar (optional)",
    )
