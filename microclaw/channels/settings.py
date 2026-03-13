import enum

from pydantic import BaseModel


class ChannelTypeEnum(str, enum.Enum):
    TELEGRAM = "telegram"
    CLI = "cli"


class ChannelSettings(BaseModel):
    type: ChannelTypeEnum
    sessions_storage: str | None = None
    agent: str | None = None
    stt: str | None = None
