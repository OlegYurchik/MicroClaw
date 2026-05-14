from pydantic import BaseModel

from microclaw.toolkits.enums import PermissionModeEnum


class UserCronsSettings(BaseModel):
    create_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
    delete_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
