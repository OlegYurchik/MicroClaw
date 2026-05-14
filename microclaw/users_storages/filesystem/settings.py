import pathlib
from typing import Literal

from microclaw.users_storages.settings import (
    UsersStorageSettings,
    UsersStorageTypeEnum,
)


class FilesystemUsersStorageSettings(UsersStorageSettings):
    type: Literal[UsersStorageTypeEnum.FILESYSTEM] = UsersStorageTypeEnum.FILESYSTEM
    path: pathlib.Path = pathlib.Path.cwd() / ".users"
