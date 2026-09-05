from typing import Literal

from metaorm import RepositorySettings

from microclaw.sessions_storages.settings import (
    SessionsStorageSettings,
    SessionsStorageTypeEnum,
)


class DatabaseSessionsStorageSettings(SessionsStorageSettings, RepositorySettings):
    type: Literal[SessionsStorageTypeEnum.DATABASE] = SessionsStorageTypeEnum.DATABASE
