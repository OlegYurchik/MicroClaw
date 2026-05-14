import fastapi

from . import handlers


def get_router() -> fastapi.APIRouter:
    router = fastapi.APIRouter()

    router.add_api_route(
        path="/",
        methods=["GET"],
        endpoint=handlers.list_users,
    )
    router.add_api_route(
        path="/",
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
    )

    return router
