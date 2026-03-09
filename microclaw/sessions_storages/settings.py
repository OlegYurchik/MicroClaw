import enum

from pydantic import BaseModel


class SessionsStorageTypeEnum(str, enum.Enum):
    MEMORY = "memory"
    FILESYSTEM = "filesystem"


class SessionsStorageSettings(BaseModel):
    type: SessionsStorageTypeEnum = SessionsStorageTypeEnum.FILESYSTEM
