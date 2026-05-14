import enum

from pydantic import BaseModel


class SyncerTypeEnum(str, enum.Enum):
    MEMORY = "memory"


class SyncerSettings(BaseModel):
    type: SyncerTypeEnum = SyncerTypeEnum.MEMORY
