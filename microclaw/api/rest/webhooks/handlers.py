import uuid

from .schemas import WebhookCreateRequest, WebhookListResponse, WebhookResponse
import fastapi
from fastapi.responses import JSONResponse

from microclaw.api.rest.dependencies import auth
from microclaw.api.rest.dependencies import resolver as resolver_dependency
from microclaw.api.rest.dependencies import users_storage as users_storage_dependency
from microclaw.api.rest.exceptions import HTTPForbidden, HTTPNotFound
from microclaw.dto import User, UserRoleEnum, Webhook
from microclaw.resolver import DependencyResolver
from microclaw.users_storages import UsersStorageInterface
from microclaw.users_storages.dto import WebhookCreate
from microclaw.users_storages.filters import WebhookFilter
from microclaw.webhooks import get_webhook as _get_webhook_impl
from microclaw.webhooks.settings import WebhookSettings


async def list_webhooks(
    user_id: uuid.UUID | None = fastapi.Query(default=None),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dependency),
    current_user: User = fastapi.Depends(auth),
) -> WebhookListResponse:
    if current_user.role != UserRoleEnum.ADMIN:
        if user_id is not None and user_id != current_user.id:
            raise HTTPForbidden()
        user_id = current_user.id

    items: list[Webhook] = []
    if user_id is not None:
        async for webhook in users_storage.get_webhooks(
            filter_=WebhookFilter(user_id={user_id}),
        ):
            items.append(webhook)
    else:
        async for webhook in users_storage.get_webhooks():
            items.append(webhook)

    return WebhookListResponse.from_items(items=items)


async def get_webhook(
    webhook_id: uuid.UUID = fastapi.Path(),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dependency),
    current_user: User = fastapi.Depends(auth),
) -> WebhookResponse:
    webhook: Webhook | None = None
    if current_user.role != UserRoleEnum.ADMIN:
        async for w in users_storage.get_webhooks(
            filter_=WebhookFilter(id={webhook_id}, user_id={current_user.id}),
        ):
            webhook = w
            break
    else:
        async for w in users_storage.get_webhooks(
            filter_=WebhookFilter(id={webhook_id}),
        ):
            webhook = w
            break

    if webhook is None:
        raise HTTPNotFound()

    return WebhookResponse.from_item(item=webhook)


async def create_webhook(
    request: WebhookCreateRequest = fastapi.Body(embed=False),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dependency),
    current_user: User = fastapi.Depends(auth),
) -> WebhookResponse:
    target_user_id = request.user_id
    if current_user.role != UserRoleEnum.ADMIN:
        if target_user_id is not None and target_user_id != current_user.id:
            raise HTTPForbidden()
        target_user_id = current_user.id
    elif target_user_id is None:
        target_user_id = current_user.id

    webhook = await users_storage.create_webhook(
        data=WebhookCreate(
            user_id=target_user_id,
            path=request.path,
            enabled=request.enabled,
            args=request.args,
            agent=request.agent,
            channel=request.channel,
            channel_internal_id=request.channel_internal_id,
        )
    )

    return WebhookResponse.from_item(item=webhook)


async def delete_webhook(
    webhook_id: uuid.UUID = fastapi.Path(),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dependency),
    current_user: User = fastapi.Depends(auth),
) -> None:
    if current_user.role != UserRoleEnum.ADMIN:
        found = False
        async for webhook in users_storage.get_webhooks(
            filter_=WebhookFilter(id={webhook_id}, user_id={current_user.id}),
        ):
            found = True
            break
        if not found:
            raise HTTPNotFound()
    else:
        found = False
        async for webhook in users_storage.get_webhooks(
            filter_=WebhookFilter(id={webhook_id}),
        ):
            found = True
            break
        if not found:
            raise HTTPNotFound()

    await users_storage.delete_webhook(
        filter_=WebhookFilter(id={webhook_id})
    )


async def call_webhook(
    request: fastapi.Request,
    webhook_id: uuid.UUID = fastapi.Path(),
    resolver: DependencyResolver = fastapi.Depends(resolver_dependency),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dependency),
) -> fastapi.Response:
    # Search in global webhooks
    global_webhooks = await resolver.resolve_global_webhooks()
    webhook_instance = global_webhooks.get(webhook_id)

    # Search in user webhooks
    if webhook_instance is None:
        async for webhook in users_storage.get_webhooks(
            filter_=WebhookFilter(id={webhook_id}),
        ):
            if not webhook.enabled:
                raise HTTPNotFound()
            args = {
                **webhook.args,
                "agent": webhook.agent,
                "channel": webhook.channel,
                "channel_internal_id": webhook.channel_internal_id,
            }
            settings = WebhookSettings(
                path=webhook.path,
                enabled=webhook.enabled,
                args=args,
            )
            webhook_instance = await _get_webhook_impl(
                settings=settings,
                resolver=resolver,
            )
            break

    if webhook_instance is None:
        raise HTTPNotFound()

    payload = await request.json()
    result = await webhook_instance(payload)

    if result is None:
        return fastapi.Response(status_code=200)

    return JSONResponse(
        content=result.body,
        status_code=result.status_code,
        headers=result.headers,
    )
