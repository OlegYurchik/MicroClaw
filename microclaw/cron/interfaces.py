from typing import Protocol
import uuid

from microclaw.dto import CronTask
from microclaw.resolver import DependencyResolver


class CronServiceInterface(Protocol):
    async def schedule(
        self,
        user_id: uuid.UUID,
        cron_task: CronTask,
        resolver: DependencyResolver,
    ) -> None:
        raise NotImplementedError

    async def unschedule(self, cron_id: uuid.UUID) -> None:
        raise NotImplementedError
