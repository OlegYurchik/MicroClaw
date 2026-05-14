from typing import Literal

from microclaw.users_storages.settings import UsersStorageSettings, UsersStorageTypeEnum


class MemoryUsersStorageSettings(UsersStorageSettings):
    type: Literal[UsersStorageTypeEnum.MEMORY] = UsersStorageTypeEnum.MEMORY
