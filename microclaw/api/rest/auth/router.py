from . import handlers
import fastapi

from microclaw.api.rest.dependencies import is_admin


def get_router() -> fastapi.APIRouter:
    router = fastapi.APIRouter()
    router.add_api_route(
        "/me",
        methods=["GET"],
        endpoint=handlers.me,
    )
    router.add_api_route(
        "/tokens",
        methods=["POST"],
        endpoint=handlers.create_token,
        dependencies=[fastapi.Depends(is_admin)],
    )
    router.add_api_route(
        "/tokens/{token}",
        methods=["DELETE"],
        endpoint=handlers.delete_token,
        dependencies=[fastapi.Depends(is_admin)],
        status_code=fastapi.status.HTTP_204_NO_CONTENT,
    )
    return router
