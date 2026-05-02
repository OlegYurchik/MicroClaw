from pydantic import BaseModel, Field

from microclaw.toolkits.enums import PermissionModeEnum


class CalDAVSettings(BaseModel):
    url: str
    username: str
    password: str
    verify_ssl: bool = True
    default_calendar_path: str | None = None
    allowed_calendars: list[str] | None = None

    write_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
