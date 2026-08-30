from collections.abc import Callable
import uuid

from .base import BaseCronTask
from .fabric import get_cron_task
from .settings import CronTaskSettings

from microclaw.dto import CronTask
from microclaw.resolver import DependencyResolver


class CronService:
    def __init__(
        self,
        task_factory: Callable[
            [str, CronTaskSettings, DependencyResolver], BaseCronTask
        ]
        | None = None,
    ):
        self._task_factory = task_factory or get_cron_task

    async def schedule(
        self,
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
        task = await self._task_factory(key=key, settings=settings, resolver=resolver)
        await task.start()

    async def unschedule(self, cron_id: uuid.UUID) -> None:
        BaseCronTask.unregister_by_cron_id(str(cron_id))
