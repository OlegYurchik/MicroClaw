import functools

import fastapi
from fastapi_openai_compat import create_chat_completion_router

from microclaw.api.rest.openai.handlers import list_models, run_completion


def get_router(app: fastapi.FastAPI):
    resolver = app.state.resolver
    sessions_storage = app.state.sessions_storage

    return create_chat_completion_router(
        list_models=functools.partial(list_models, resolver=resolver),
        run_completion=functools.partial(
            run_completion,
            resolver=resolver,
            sessions_storage=sessions_storage,
        ),
        include_models_endpoints=True,
    )
