import facet
import uvicorn

import fastapi

from microclaw.resolver import DependencyResolver
from microclaw.sessions_storages import (
    SessionsStorageSettingsType,
    get_sessions_storage,
)
from microclaw.users_storages import UsersStorageSettingsType, get_users_storage
from microclaw.utils import get_by_key_or_first
from . import sessions, users
from .settings import RESTAPISettings


class UvicornServer(uvicorn.Server):
    def install_signal_handlers(self):
        pass


class RESTAPIService(facet.AsyncioServiceMixin):
    def __init__(
        self,
        settings: RESTAPISettings,
        dependency_resolver: DependencyResolver,
    ):
        self._settings = settings
        self._dependency_resolver = dependency_resolver

    async def start(self):
        config = uvicorn.Config(
            app=self.get_app(),
            host=self._settings.host,
            port=self._settings.port,
        )
        server = UvicornServer(config)

        self.add_task(server.serve())

    def get_app(self) -> fastapi.FastAPI:
        app = fastapi.FastAPI(
            root_url=self._settings.root_url,
            root_path=self._settings.root_path,
        )

        await self.setup_app(app=app)

        return app

    async def setup_app(self, app: fastapi.FastAPI):
        if isinstance(self._settings.users_storage, UsersStorageSettingsType):
            app.users_storage = get_users_storage(settings=self._settings.users_storage)
        else:
            app.users_storage = get_by_key_or_first(
                storage=await self._dependency_resolver.resolve_users_storages(),
                key=self._settings.users_storage,
            )
        if isinstance(self._settings.sessions_storage, SessionsStorageSettingsType):
            app.sessions_storage = get_sessions_storage(
                settings=self._settings.sessions_storage
            )
        else:
            app.sessions_storage = get_by_key_or_first(
                storage=await self._dependency_resolver.resolve_sessions_storages(),
                key=self._settings.sessions_storage,
            )

        app.include_router(users.get_router(), prefix="/users")
        app.include_router(sessions.get_router(), prefix="/sessions")
