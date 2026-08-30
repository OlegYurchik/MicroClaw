from . import handlers
import fastapi


def get_router() -> fastapi.APIRouter:
    router = fastapi.APIRouter()
    router.add_api_route(path="", methods=["GET"], endpoint=handlers.list_agents)
    router.add_api_route(path="/{id}", methods=["GET"], endpoint=handlers.get_agent)
    return router
