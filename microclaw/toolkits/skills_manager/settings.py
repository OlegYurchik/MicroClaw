from pydantic import BaseModel

from microclaw.toolkits.enums import PermissionModeEnum, SourceModeEnum


class SkillsManagerToolKitSettings(BaseModel):
    skills_directory: str = "./.skills"
    install_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
    remove_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
    update_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
    enable_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
    source_mode: SourceModeEnum = SourceModeEnum.ALL
