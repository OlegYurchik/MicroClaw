from typing import Literal

from microclaw.sessions_storages.settings import (
    SessionsStorageSettings,
    SessionsStorageTypeEnum,
)


class MemorySessionsStorageSettings(SessionsStorageSettings):
    type: Literal[SessionsStorageTypeEnum.MEMORY] = SessionsStorageTypeEnum.MEMORY
