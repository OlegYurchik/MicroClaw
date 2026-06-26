from typing import Literal

from pydantic import BaseModel, Field


class PackageIndexCredentials(BaseModel):
    username: str | None = None
    password: str | None = None


class PackageIndexSettings(BaseModel):
    url: str
    priority: Literal["primary", "secondary"] = "secondary"
    credentials: PackageIndexCredentials | None = None
    trusted: bool = False


class PackageSettings(BaseModel):
    name: str
    version: str | None = None
    extras: list[str] = Field(default_factory=list)
    repository: str | None = None


class ExtraPackagesSettings(BaseModel):
    dir: str | None = None
    indexes: dict[str, PackageIndexSettings] = Field(default_factory=dict)
    packages: list[PackageSettings] = Field(default_factory=list)
