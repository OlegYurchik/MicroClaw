from typing import TypeVar, Generic

import asyncio
import facet
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from pydantic import BaseModel

from .settings import CronTaskSettings


SettingsType = TypeVar("SettingsType")


class EmptySettings(BaseModel):
    pass


class BaseCronTask(facet.AsyncioServiceMixin, Generic[SettingsType]):
    _scheduler: AsyncIOScheduler | None = None
    _tasks: dict[str, "BaseCronTask"] = {}

    def __init__(
        self,
        key: str,
        settings: CronTaskSettings,
        resolver: "DependencyResolver",  # noqa: F821
    ):
        self._key = key
        self._cron = settings.cron
        self._settings = self.get_settings_class()(**settings.args)
        self._resolver = resolver

    @classmethod
    def get_settings_class(cls) -> type[SettingsType] | type[EmptySettings]:
        for base in cls.__orig_bases__:
            origin = getattr(base, "__origin__", None)
            if isinstance(origin, type) and issubclass(origin, BaseCronTask):
                return base.__args__[0]
        return EmptySettings

    async def start(self):
        scheduler = self.get_scheduler()
        if not scheduler.running:
            scheduler.start()
            logger.info("Cron scheduler started")

        if self._key in self._tasks:
            logger.warning(f"Task '{self._key}' already registered, replacing")
            return

        await self.do_before()

        scheduler.add_job(
            self._execute_with_logging,
            "cron",
            id=self._key,
            **self._parse_cron_expression(self._cron),
        )
        self._tasks[self._key] = self
        logger.info(f"Task '{self._key}' registered with cron: {self._cron}")

        self.add_task(self._wait_for_scheduler())

    @classmethod
    def get_scheduler(cls) -> AsyncIOScheduler:
        if cls._scheduler is None:
            cls._scheduler = AsyncIOScheduler()
        return cls._scheduler

    async def do_before(self):
        pass

    async def stop(self):
        scheduler = self.get_scheduler()
        if scheduler.get_job(self._key):
            scheduler.remove_job(self._key)
        if self._key in self._tasks:
            del self._tasks[self._key]
            logger.info(f"Task '{self._key}' unregistered")

    async def _wait_for_scheduler(self):
        scheduler = self.get_scheduler()
        while scheduler.running:
            await asyncio.sleep(1)

    def _parse_cron_expression(self, cron_expr: str) -> dict:
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression: {cron_expr}. "
                f"Expected format: 'minute hour day month day_of_week'"
            )
        minute, hour, day, month, day_of_week = parts

        return {
            "minute": minute,
            "hour": hour,
            "day": day,
            "month": month,
            "day_of_week": day_of_week,
        }

    async def _execute_with_logging(self):
        logger.info(f"Starting cron task '{self._key}'")
        try:
            await self.execute()
            logger.info(f"Completed cron task '{self._key}'")
        except Exception as e:
            logger.error(f"Error in cron task '{self._key}': {e}")
            raise

    async def execute(self):
        raise NotImplementedError
