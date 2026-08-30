from . import agents, auth, crons, handlers, models, sessions, toolkits, users
from .dependencies import auth as auth_dependency
from .openai import get_router as get_openai_router
from .settings import RESTAPISettings
import facet
import fastapi
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from microclaw.resolver import DependencyResolver
from microclaw.sessions_storages import (
    SessionsStorageSettingsType,
    get_sessions_storage,
)
from microclaw.users_storages import UsersStorageSettingsType, get_users_storage
from microclaw.utils import get_by_key_or_first


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
        app = await self._build_app()
        config = uvicorn.Config(
            app=app,
            host=self._settings.host,
            port=self._settings.port,
        )
        server = UvicornServer(config)

        self.add_task(server.serve())

    async def _build_app(self) -> fastapi.FastAPI:
        app = fastapi.FastAPI()
        await self._setup_app(app=app)
        return app

    async def _setup_app(self, app: fastapi.FastAPI):
        if isinstance(self._settings.users_storage, UsersStorageSettingsType):
            app.state.users_storage = get_users_storage(
                settings=self._settings.users_storage
            )
        else:
            app.state.users_storage = get_by_key_or_first(
                storage=await self._dependency_resolver.resolve_users_storages(),
                key=self._settings.users_storage,
            )
        if isinstance(self._settings.sessions_storage, SessionsStorageSettingsType):
            app.state.sessions_storage = get_sessions_storage(
                settings=self._settings.sessions_storage
            )
        else:
            app.state.sessions_storage = get_by_key_or_first(
                storage=await self._dependency_resolver.resolve_sessions_storages(),
                key=self._settings.sessions_storage,
            )

        app.state.resolver = self._dependency_resolver

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        app.include_router(
            get_openai_router(app),
            prefix="/openai",
            dependencies=[fastapi.Depends(auth_dependency)],
        )
        app.include_router(auth.get_router(), prefix="/auth")
        app.include_router(
            agents.get_router(),
            prefix="/agents",
        )
        app.include_router(
            crons.get_router(),
            prefix="/crons",
        )
        app.include_router(
            models.get_router(),
            prefix="/models",
        )
        app.include_router(
            toolkits.get_router(),
            prefix="/toolkits",
        )
        app.include_router(users.get_router(), prefix="/users")
        app.include_router(sessions.get_router(), prefix="/sessions")

        app.get("/health")(handlers.health)
