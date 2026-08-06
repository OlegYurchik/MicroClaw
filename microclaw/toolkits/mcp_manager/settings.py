from pydantic import BaseModel

from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum


class MCPManagerToolKitSettings(BaseModel):
    add_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
    remove_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
    source_mode: SourceModeEnum = SourceModeEnum.ALL
