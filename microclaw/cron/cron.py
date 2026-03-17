import logging
import uuid

import facet
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from microclaw.channels.interfaces import ChannelInterface
from microclaw.dto import AgentMessage
from microclaw.cron.settings import CronSettings


logger = logging.getLogger(__name__)


class Cron(facet.AsyncioServiceMixin):
    def __init__(
            self,
            settings: CronSettings,
            channel: ChannelInterface,
    ):
        self._settings = settings
        self._channel = channel
        self._scheduler = AsyncIOScheduler()

    async def start(self):
        self._scheduler.add_job(
            self._run_scheduled_task,
            "cron",
            **self._parse_cron_expression(self._settings.cron),
        )
        self._scheduler.start()

    def _parse_cron_expression(self, cron_expr: str) -> dict:
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expr}. Expected format: '* * * * *'")
        minute, hour, day, month, day_of_week = parts

        return {
            "minute": minute,
            "hour": hour,
            "day": day,
            "month": month,
            "day_of_week": day_of_week,
        }

    async def _run_scheduled_task(self):
        logger.info("Run scheduled task")

        messages = [
            AgentMessage(
                role="system",
                text=self._settings.task,
            ),
        ]
        
        session_id = uuid.uuid4()
        channel_args = self._settings.channel_args or {}
        await self._channel.start_conversation(
            session_id=session_id,
            messages=messages,
            **channel_args,
        )

    async def stop(self):
        self._scheduler.shutdown()
