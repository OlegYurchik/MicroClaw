from typing import Literal

from metaorm import RepositorySettings

from microclaw.users_storages.settings import UsersStorageSettings, UsersStorageTypeEnum


class DatabaseUsersStorageSettings(UsersStorageSettings, RepositorySettings):
    type: Literal[UsersStorageTypeEnum.DATABASE] = UsersStorageTypeEnum.DATABASE
