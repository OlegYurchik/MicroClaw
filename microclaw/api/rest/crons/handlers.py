import uuid

import fastapi

from microclaw.api.rest.dependencies import auth, resolver as resolver_dependency, users_storage as users_storage_dependency
from microclaw.api.rest.exceptions import HTTPForbidden, HTTPNotFound
from microclaw.dto import CronTask, User, UserRoleEnum
from microclaw.cron import BaseCronTask, CronTaskSettings, get_cron_task
from microclaw.resolver import DependencyResolver
from microclaw.users_storages import UsersStorageInterface

from .schemas import CronTaskCreateRequest, CronTaskListResponse, CronTaskResponse


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
    if user_id is not None:
        items = await users_storage.get_crons(user_id=user_id)
    else:
        async for user in users_storage.get_users():
            user_crons = await users_storage.get_crons(user_id=user.id)
            for user_cron in user_crons:
                items.append(user_cron)

    return CronTaskListResponse.from_items(items=items)


async def create_cron(
    request: CronTaskCreateRequest = fastapi.Body(embed=False),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dependency),
    resolver: DependencyResolver = fastapi.Depends(resolver_dependency),
    current_user: User = fastapi.Depends(auth),
) -> CronTaskResponse:
    target_user_id = request.user_id
    if current_user.role != UserRoleEnum.ADMIN:
        if target_user_id is not None and target_user_id != current_user.id:
            raise HTTPForbidden()
        target_user_id = current_user.id
    elif target_user_id is None:
        target_user_id = current_user.id

    cron_task = CronTask(
        id=uuid.uuid4(),
        path=request.path,
        cron=request.cron,
        enabled=request.enabled,
        args=request.args,
    )
    await users_storage.create_cron(user_id=target_user_id, cron_task=cron_task)

    if request.enabled:
        await _schedule_cron(
            target_user_id,
            cron_task,
            resolver,
        )

    return CronTaskResponse.from_item(item=cron_task)


async def delete_cron(
    cron_id: uuid.UUID = fastapi.Path(),
    users_storage: UsersStorageInterface = fastapi.Depends(users_storage_dependency),
    current_user: User = fastapi.Depends(auth),
) -> None:
    if current_user.role != UserRoleEnum.ADMIN:
        user_crons = await users_storage.get_crons(user_id=current_user.id)
        if not any(cron.id == cron_id for cron in user_crons):
            raise HTTPNotFound()
    else:
        found = False
        async for user in users_storage.get_users():
            user_crons = await users_storage.get_crons(user_id=user.id)
            if any(cron.id == cron_id for cron in user_crons):
                found = True
                break
        if not found:
            raise HTTPNotFound()

    await users_storage.remove_cron(cron_id=cron_id)
    await _unschedule_cron(cron_id)

async def _schedule_cron(
    user_id: uuid.UUID,
    cron_task: CronTask,
    resolver: DependencyResolver,
) -> None:
    settings = CronTaskSettings(
        path=cron_task.path,
        cron=cron_task.cron,
        enabled=cron_task.enabled,
        args=cron_task.args,
    )
    key = f"rest_{user_id}_{cron_task.id}"
    task = await get_cron_task(key=key, settings=settings, resolver=resolver)
    await task.start()


async def _unschedule_cron(cron_id: uuid.UUID) -> None:
    scheduler = BaseCronTask.get_scheduler()
    for key in list(BaseCronTask._tasks.keys()):
        if key.endswith(str(cron_id)):
            if scheduler.running and scheduler.get_job(key):
                scheduler.remove_job(key)
            if key in BaseCronTask._tasks:
                del BaseCronTask._tasks[key]
            break
