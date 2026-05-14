import enum

from pydantic import BaseModel


class UsersStorageTypeEnum(str, enum.Enum):
    MEMORY = "memory"
    FILESYSTEM = "filesystem"
    DATABASE = "database"


class UsersStorageSettings(BaseModel):
    type: UsersStorageTypeEnum = UsersStorageTypeEnum.MEMORY
