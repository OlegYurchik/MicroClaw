import pathlib
from typing import Literal

from .enums import SkillRepositoryTypeEnum
from .types import SkillNameType
from pydantic import BaseModel


class SkillRepositoryBaseSettings(BaseModel):
    type: SkillRepositoryTypeEnum


class SkillRepositoryLocalSettings(SkillRepositoryBaseSettings):
    type: Literal[SkillRepositoryTypeEnum.LOCAL] = SkillRepositoryTypeEnum.LOCAL
    directory: pathlib.Path


class SkillRepositoryGitHubSettings(SkillRepositoryBaseSettings):
    type: Literal[SkillRepositoryTypeEnum.GITHUB] = SkillRepositoryTypeEnum.GITHUB
    url: str


SkillRepositorySettingsType = (
    SkillRepositoryLocalSettings | SkillRepositoryGitHubSettings
)


class SkillSettings(BaseModel):
    name: SkillNameType
    repo: SkillRepositorySettingsType | str | None = None
