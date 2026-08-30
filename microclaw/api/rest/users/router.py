from . import handlers
import fastapi


def get_router() -> fastapi.APIRouter:
    router = fastapi.APIRouter()

    router.add_api_route(
        path="",
        methods=["GET"],
        endpoint=handlers.list_users,
    )
    router.add_api_route(
        path="",
        methods=["POST"],
        endpoint=handlers.create_user,
    )
    router.add_api_route(
        path="/{user_id}",
        methods=["GET"],
        endpoint=handlers.get_user,
    )
    router.add_api_route(
        path="/{user_id}",
        methods=["PATCH"],
        endpoint=handlers.update_user,
    )
    router.add_api_route(
        path="/{user_id}",
        methods=["DELETE"],
        endpoint=handlers.delete_user,
        status_code=fastapi.status.HTTP_204_NO_CONTENT,
    )
    router.add_api_route(
        path="/{user_id}/sessions",
        methods=["GET"],
        endpoint=handlers.list_user_sessions,
    )
    router.add_api_route(
        path="/{user_id}/tokens",
        methods=["POST"],
        endpoint=handlers.create_user_token,
    )
    router.add_api_route(
        path="/{user_id}/tokens/{token}",
        methods=["DELETE"],
        endpoint=handlers.delete_user_token,
        status_code=fastapi.status.HTTP_204_NO_CONTENT,
    )

    return router
