from pydantic import BaseModel

from microclaw.toolkits.enums import PermissionModeEnum


class AgentsToolKitSettings(BaseModel):
    set_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
    reset_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
