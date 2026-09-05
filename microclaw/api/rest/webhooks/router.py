from . import handlers
import fastapi


def get_router() -> fastapi.APIRouter:
    router = fastapi.APIRouter()

    # Management (with auth)
    router.add_api_route(
        path="",
        methods=["GET"],
        endpoint=handlers.list_webhooks,
    )
    router.add_api_route(
        path="",
        methods=["POST"],
        endpoint=handlers.create_webhook,
    )
    router.add_api_route(
        path="/{webhook_id}",
        methods=["GET"],
        endpoint=handlers.get_webhook,
    )
    router.add_api_route(
        path="/{webhook_id}",
        methods=["DELETE"],
        endpoint=handlers.delete_webhook,
        status_code=fastapi.status.HTTP_204_NO_CONTENT,
    )

    # Call (no auth)
    router.add_api_route(
        path="/{webhook_id}/call",
        methods=["POST"],
        endpoint=handlers.call_webhook,
    )

    return router
