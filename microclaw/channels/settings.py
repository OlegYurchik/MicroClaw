import enum

from pydantic import BaseModel

from microclaw.agents import AgentSettings
from microclaw.sessions_storages import SessionsStorageSettingsType
from microclaw.stt import STTSettings
from microclaw.users_storages import UsersStorageSettingsType


class ChannelTypeEnum(str, enum.Enum):
    TELEGRAM = "telegram"
    CLI = "cli"
    MATRIX = "matrix"


class ChannelSettings(BaseModel):
    type: ChannelTypeEnum
    sessions_storage: SessionsStorageSettingsType | str | None = None
    users_storage: UsersStorageSettingsType | str | None = None
    agent: AgentSettings | str | None = None
    stt: STTSettings | str | None = None
