from typing import Literal

from microclaw.users_storages.settings import (
    UsersStorageSettings,
    UsersStorageTypeEnum,
)
from microclaw.utils.database.settings import DatabaseSettings


class DatabaseUsersStorageSettings(UsersStorageSettings, DatabaseSettings):
    type: Literal[UsersStorageTypeEnum.DATABASE] = UsersStorageTypeEnum.DATABASE
