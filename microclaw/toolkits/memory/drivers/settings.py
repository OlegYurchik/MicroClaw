import enum

from pydantic import BaseModel


class MemoryDriverEnum(str, enum.Enum):
    FILESYSTEM = "filesystem"


class MemoryDriverSettings(BaseModel):
    type: MemoryDriverEnum