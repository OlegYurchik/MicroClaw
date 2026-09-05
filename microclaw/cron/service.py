from collections.abc import Callable
import uuid

from .base import BaseCronTask
from .fabric import get_cron_task
from .settings import CronTaskSettings
import facet

from microclaw.dto import CronTask
from microclaw.resolver import DependencyResolver


class CronService(facet.AsyncioServiceMixin):
    def __init__(
        self,
        crons: dict[str, BaseCronTask] | None = None,
        task_factory: Callable[
            [str, CronTaskSettings, DependencyResolver], BaseCronTask
        ]
        | None = None,
    ):
        self._crons = crons or {}
        self._task_factory = task_factory or get_cron_task

    @property
    def dependencies(self) -> list[facet.AsyncioServiceMixin]:
        return list(self._crons.values())

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
        self._crons[key] = task
        BaseCronTask.register_cron_id(str(cron_task.id), key)

    async def unschedule(self, cron_id: uuid.UUID) -> None:
        """Unschedule a dynamically scheduled cron by its CronTask.id.

        Note: This only works for crons scheduled via :meth:`schedule`
        (keys ending with a UUID). System crons loaded from settings use
        arbitrary string keys and must be stopped via the service lifecycle.
        """
        scheduler = BaseCronTask.get_scheduler()
        cron_id_str = str(cron_id)
        key = BaseCronTask.find_task_key_by_cron_id(cron_id_str)
        if key is not None:
            if scheduler.get_job(key):
                scheduler.remove_job(key)
            task = self._crons.pop(key, None)
            if task is not None:
                await task.stop()
            else:
                BaseCronTask.unregister_task(key)
        BaseCronTask.unregister_cron_id(cron_id_str)
