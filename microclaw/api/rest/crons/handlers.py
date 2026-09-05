import uuid

from .schemas import CronTaskCreateRequest, CronTaskListResponse, CronTaskResponse
import fastapi

from microclaw.api.rest.dependencies import auth
from microclaw.api.rest.dependencies import cron_service as cron_service_dependency
from microclaw.api.rest.dependencies import resolver as resolver_dependency
from microclaw.api.rest.dependencies import users_storage as users_storage_dependency
from microclaw.api.rest.exceptions import HTTPForbidden, HTTPNotFound
from microclaw.cron.interfaces import CronServiceInterface
from microclaw.dto import CronTask, User, UserRoleEnum
from microclaw.resolver import DependencyResolver
from microclaw.users_storages import UsersStorageInterface
from microclaw.users_storages.dto import CronCreate
from microclaw.users_storages.filters import CronFilter


async def list_crons(
    user_id: uuid.UUID | None = fastapi.Query(default=None),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dependency),
    current_user: User = fastapi.Depends(auth),
) -> CronTaskListResponse:
    if current_user.role != UserRoleEnum.ADMIN:
        if user_id is not None and user_id != current_user.id:
            raise HTTPForbidden()
        user_id = current_user.id

    items: list[CronTask] = []
    filter_ = CronFilter(user_id={user_id}) if user_id is not None else None
    async for cron in users_storage.get_crons(filter_=filter_):
        items.append(cron)

    return CronTaskListResponse.from_items(items=items)


async def create_cron(
    request: CronTaskCreateRequest = fastapi.Body(embed=False),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dependency),
    resolver: DependencyResolver = fastapi.Depends(resolver_dependency),
    current_user: User = fastapi.Depends(auth),
    cron_service: CronServiceInterface = fastapi.Depends(cron_service_dependency),
) -> CronTaskResponse:
    target_user_id = request.user_id
    if current_user.role != UserRoleEnum.ADMIN:
        if target_user_id is not None and target_user_id != current_user.id:
            raise HTTPForbidden()
        target_user_id = current_user.id
    elif target_user_id is None:
        target_user_id = current_user.id

    cron_task = await users_storage.create_cron(
        data=CronCreate(
            user_id=target_user_id,
            path=request.path,
            cron=request.cron,
            enabled=request.enabled,
            args=request.args,
        )
    )

    if request.enabled:
        await cron_service.schedule(
            target_user_id,
            cron_task,
            resolver,
        )

    return CronTaskResponse.from_item(item=cron_task)


async def delete_cron(
    cron_id: uuid.UUID = fastapi.Path(),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dependency),
    current_user: User = fastapi.Depends(auth),
    cron_service: CronServiceInterface = fastapi.Depends(cron_service_dependency),
) -> None:
    if current_user.role != UserRoleEnum.ADMIN:
        cron = await users_storage.get_cron(
            filter_=CronFilter(id={cron_id}, user_id={current_user.id})
        )
        if cron is None:
            raise HTTPNotFound()
    else:
        cron = await users_storage.get_cron(filter_=CronFilter(id={cron_id}))
        if cron is None:
            raise HTTPNotFound()

    await users_storage.delete_cron(
        filter_=CronFilter(id={cron_id})
    )
    await cron_service.unschedule(cron_id)
