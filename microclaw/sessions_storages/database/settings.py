from typing import Literal

from microclaw.sessions_storages.settings import (
    SessionsStorageSettings,
    SessionsStorageTypeEnum,
)
from microclaw.utils.database.settings import DatabaseSettings


class DatabaseSessionsStorageSettings(SessionsStorageSettings, DatabaseSettings):
    type: Literal[SessionsStorageTypeEnum.DATABASE] = SessionsStorageTypeEnum.DATABASE
