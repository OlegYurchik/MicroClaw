from . import handlers
import fastapi


def get_router() -> fastapi.APIRouter:
    router = fastapi.APIRouter()

    router.add_api_route(
        path="",
        methods=["GET"],
        endpoint=handlers.list_crons,
    )
    router.add_api_route(
        path="",
        methods=["POST"],
        endpoint=handlers.create_cron,
    )
    router.add_api_route(
        path="/{cron_id}",
        methods=["DELETE"],
        endpoint=handlers.delete_cron,
        status_code=fastapi.status.HTTP_204_NO_CONTENT,
    )

    return router
