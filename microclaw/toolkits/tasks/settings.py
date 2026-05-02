from pydantic import BaseModel, Field

from microclaw.toolkits.enums import PermissionModeEnum


class TasksSettings(BaseModel):
    """Settings for connecting to Nextcloud Tasks via CalDAV."""

    url: str = Field(
        description=(
            "URL of the CalDAV server for Nextcloud Tasks "
            "(e.g., https://cloud.example.com/remote.php/dav/calendars/username/)"
        ),
    )
    username: str = Field(description="Username for authentication")
    password: str = Field(description="Password or app password for authentication")
    verify_ssl: bool = Field(
        default=True,
        description="Verify SSL certificate (default: True)",
    )
    allowed_task_lists: list[str] | None = None
    write_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
