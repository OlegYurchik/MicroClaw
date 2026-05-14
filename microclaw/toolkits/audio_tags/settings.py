import pathlib

from pydantic import BaseModel, Field

from microclaw.toolkits.enums import PermissionModeEnum


class AudioTagsToolKitSettings(BaseModel):
    directories: list[str] = Field(
        default_factory=lambda: [str(pathlib.Path.cwd())],
    )
    write_mode: PermissionModeEnum = PermissionModeEnum.REQUEST
