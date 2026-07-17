from pydantic import BaseModel

from microclaw.toolkits.enums import PermissionModeEnum


class AgentConfigToolKitSettings(BaseModel):
    reset_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
