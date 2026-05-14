from pydantic import BaseModel, conint

from microclaw.sessions_storages import SessionsStorageSettingsType
from microclaw.users_storages import UsersStorageSettingsType


class RESTAPISettings(BaseModel):
    host: str = "127.0.0.1"
    port: conint(ge=1, le=65535) = 8000

    users_storage: UsersStorageSettingsType | str | None = None
    sessions_storage: SessionsStorageSettingsType | str | None = None
