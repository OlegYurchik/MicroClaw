from . import handlers
import fastapi


def get_router() -> fastapi.APIRouter:
    router = fastapi.APIRouter()

    router.add_api_route(
        path="",
        methods=["POST"],
        endpoint=handlers.create_session,
    )
    router.add_api_route(
        path="",
        methods=["GET"],
        endpoint=handlers.list_sessions,
    )
    router.add_api_route(
        path="/{session_id}",
        methods=["GET"],
        endpoint=handlers.get_session,
    )
    router.add_api_route(
        path="/{session_id}",
        methods=["DELETE"],
        endpoint=handlers.delete_session,
        status_code=fastapi.status.HTTP_204_NO_CONTENT,
    )
    router.add_api_route(
        path="/{session_id}/spending",
        methods=["GET"],
        endpoint=handlers.get_session_spending,
    )
    return router
