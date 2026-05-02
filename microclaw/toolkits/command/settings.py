from pydantic import BaseModel, Field

from microclaw.toolkits.enums import PermissionModeEnum


class CommandToolKitSettings(BaseModel):
    """Settings for the command toolkit."""

    allowed_commands: list[str] | None = None
    execute_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
