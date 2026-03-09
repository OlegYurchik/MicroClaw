import pathlib
from typing import Literal

from microclaw.sessions_storages.settings import (
    SessionsStorageSettings,
    SessionsStorageTypeEnum,
)


class FilesystemSessionsStorageSettings(SessionsStorageSettings):
    type: Literal[SessionsStorageTypeEnum.FILESYSTEM] = SessionsStorageTypeEnum.FILESYSTEM
    path: pathlib.Path = pathlib.Path.cwd() / ".sessions_storages"