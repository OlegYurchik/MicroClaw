import enum

from pydantic import BaseModel

from microclaw.toolkits.enums import PermissionModeEnum


class RuntimeTypeEnum(str, enum.Enum):
    NATIVE = "native"
    DOCKER = "docker"


class CommandToolKitSettings(BaseModel):
    runtime: RuntimeTypeEnum = RuntimeTypeEnum.NATIVE
    allowed_commands: list[str] | None = None
    deny_commands: list[str] | None = None
    execute_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
